import math
from functools import reduce
import re
from time import time
from .request import *
from .utils import *
from .logger import get_logger
import pandas as pd

def convert_value(v: str):
    try:
        if '.' in v:
            return float(v)
        return int(v)
    except ValueError:
        return v.strip()


def strip_comment(line: str):
    if "#" in line:
        line = line.split("#", 1)[0]
    return line.strip()


def load_flat_config(logger, path: str):
    spec_name = path.split("/")[-1].split(".")[0]
    logger.debug("Configuring %s", spec_name)
    data = {}

    with open(path, "r") as f:
        for line in f:
            # remote comment
            line = strip_comment(line)

            # skip empty line
            if not line or line.startswith("[") or line.startswith(";"):
                continue

            # key-value pair
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = convert_value(value.strip())
                data[key] = value

    return data

class PIMModel:
    def __init__(self, node_id, mem_size, pim_config_path):
        self.pim_config_path = pim_config_path
        self.spec_name = pim_config_path.split("/")[-1].split(".")[0]
        self.mem_size = mem_size
        self.logger = get_logger(self.__class__, node_id=node_id)
        self.init_dram_params()
        self.node_id = node_id

        self.logger.debug("spec_name: %s", self.spec_name)

        ## latency modeling test ##
        # n_head = 32
        # kv_head = 8
        # head_dim = 128

        # self.logger.debug("spec_name: %s", self.spec_name)
        # for L in range(128, 4096 + 1, 128):
        #     latency = self.estimate_with_linear(n_head, kv_head, head_dim, L)
        #     self.logger.debug("pim latency (seq %d): %.2f ns", L, latency)

    def init_dram_params(self):
        pim_config = load_flat_config(self.logger, self.pim_config_path)
        self.config = pim_config

        banks = pim_config["bankgroups"] * pim_config["banks_per_group"]
        bus_width = pim_config["bus_width"]
        device_width = pim_config["device_width"]
        columns = pim_config["columns"]
        rows = pim_config["rows"]
        channel_size = pim_config["channel_size"]
        data_rate = pim_config["data_rate"]

        # memory channel capacity 
        devices_per_rank = bus_width / device_width
        page_size = columns * device_width / 8;  # page size in bytes
        megs_per_bank = page_size * (rows / 1024) / 1024
        megs_per_rank = megs_per_bank * banks * devices_per_rank

        if megs_per_rank > channel_size:
            ranks = 1
            channel_size = megs_per_rank
        else:
            ranks = channel_size / megs_per_rank
            channel_size = ranks * megs_per_rank

        self.ch_capacity = channel_size / 1024

        # memory channel bandwidth & capacity
        self.ch_bw = bus_width / 8 * data_rate / 1000 # per_channel (GB/s)

        self.num_ch = self.mem_size / self.ch_capacity
        self.mem_bw = self.num_ch * self.ch_bw
        
        ### read latency
        CL = pim_config["CL"]
        tCK = pim_config["tCK"]
        self.read_latency = CL * tCK

        # Compute-side throughput of the PNM engine, expressed via operational
        # intensity (FLOPs/byte). NELSSA sizes the compute engine to *saturate*
        # the module's bandwidth (OI ~= 8 -> ~1.6 TFLOPS at 200 GB/s), so
        # peak_flops = mem_bw x OI. Used for compute-bound work like the
        # RetrievalAttention index build. Overridable via the .ini.
        self.operational_intensity = pim_config.get("operational_intensity", 8.0)

    def get_config(self):
        return {"mem_size": self.mem_size, 
                "mem_bw": self.mem_bw,
                "mem_latency": self.read_latency, 
                "dimm_size": self.ch_capacity}
    
    def get_pim_power(self):
        idle_power = self.config["idle_power"] / 1000 # W
        peak_power = self.config["peak_power"] / 1000 # W
        self.logger.debug("idle_power: %.2f W", idle_power)
        self.logger.debug("peak_power: %.2f W", peak_power)
        return (idle_power, peak_power)
    
    def get_pim_latency(self, n_head, kv_head, head_dim, L, channel_split=1):
        return self.estimate_with_linear(n_head, kv_head, head_dim, L, channel_split) # ns

    def get_index_build_latency(self, head_dim, n_new_tokens, kv_size):
        """Estimate the RetrievalAttention vector-index build cost (ns).

        NELSSA builds a per-layer IVF index over the prefilled KV cache and
        offloads it to the PNM modules -- a one-time upfront cost at prefill
        (SK hynix, IEEE CAL 2025). Inserting ``n_new_tokens`` key vectors into
        an IVF index with ``n_list = round(sqrt(kv_size))`` centroids costs one
        ``head_dim``-wide distance per (vector, centroid) pair. This is
        compute-bound, so it is sized by the module's compute throughput
        ``peak_flops = mem_bw x operational_intensity`` (the same bandwidth-
        saturating engine the paper describes), not by memory streaming.

        Args:
            head_dim: per-head dimension of the indexed key vectors.
            n_new_tokens: KV vectors added to the index this step.
            kv_size: total KV length backing the index (sets n_list).

        Returns:
            Latency in nanoseconds.
        """
        n_new = max(0, int(n_new_tokens))
        if n_new == 0:
            return 0.0
        n_list = max(1, round(math.sqrt(max(1, int(kv_size)))))
        macs = n_new * n_list * head_dim               # head_dim-wide distances
        peak_flops = self.mem_bw * 1e9 * self.operational_intensity  # bytes/s * FLOPs/byte
        peak_macs = peak_flops / 2.0                   # 1 MAC = 2 FLOPs
        return macs / peak_macs * 1e9                  # ns

    def _scaled_coeffs(self, n_head, kv_head, head_dim):
        """Return (slope, intercept) in ns for this spec, scaled to the model.

        Coefficients are fit against the Llama-3.1-8B baseline (n_head=32,
        kv_head=8, head_dim=128) and scaled to arbitrary architectures:
            slope scales with (n_head / kv_head) — GQA ratio
            intercept scales with (n_head * head_dim) — total KV cache size
        """
        # Baseline coefficients (Llama-3.1-8B: n_head=32, kv_head=8, head_dim=128)
        attn_model = {
            "LPDDR4X_2GB_4266_pim": {
                "slope": 432.4458,
                "intercept": 33918.1734
            },
            "DDR4_8GB_3200_pim": {
                "slope": 333.2538,
                "intercept": 30675.2739
            },
            "LPDDR5_2GB_6400_pim": {
                "slope": 282.4338,
                "intercept": 15996.7018
            },
            "HBM2_1GB_2000_pim": {
                "slope": 242.0548,
                "intercept": 14513.5015
            },
            # NELSSA HC-PNM module (4-CH DDR5-6400, 200 GB/s, 1 TB). Derived
            # from DDR4_8GB_3200_pim (identical bus_width=64 byte model) since
            # NELSSA's compute engine is provisioned to saturate the module's
            # bandwidth, making full attention bandwidth-bound:
            #   slope     scales inversely with bandwidth (2x data_rate):
            #             333.2538 * (3200 / 6400) = 166.6269
            #   intercept scales with first-word read latency (CL*tCK):
            #             30675.2739 * (12.5 / 13.86) = 27665.40
            # The slope-vs-bandwidth relation is validated by the LPDDR4X/
            # LPDDR5 pair (slope ratio 1.531 vs data_rate ratio 1.501).
            "DDR5_1TB_6400_pim": {
                "slope": 166.6269,
                "intercept": 27665.40
            },
        }

        if self.spec_name not in attn_model:
            raise ValueError(f"Unknown PIM spec: {self.spec_name}")

        base = attn_model[self.spec_name]

        # Baseline model parameters
        BASE_N_HEAD = 32
        BASE_KV_HEAD = 8
        BASE_HEAD_DIM = 128

        # Slope scales with GQA ratio (more heads = more compute per token)
        gqa_ratio = (n_head / kv_head) / (BASE_N_HEAD / BASE_KV_HEAD)
        # Intercept scales with total KV cache size (more heads * dim = more data to load)
        kv_scale = (n_head * head_dim) / (BASE_N_HEAD * BASE_HEAD_DIM)

        slope = base["slope"] * gqa_ratio
        intercept = base["intercept"] * kv_scale
        return slope, intercept

    def estimate_with_linear(self, n_head, kv_head, head_dim, L, channel_split=1):
        """Estimate full PIM attention latency (ns) via the linear model.

        Full decode attention streams the entire KV cache (length ``L``), so
        latency is bandwidth-bound: ``(slope * L + intercept) / channel_split``.
        """
        slope, intercept = self._scaled_coeffs(n_head, kv_head, head_dim)
        return (slope * L + intercept) / channel_split  # float, ns

    def get_sparse_pim_latency(self, n_head, kv_head, head_dim, L,
                               selection_ratio, nprobe=32, channel_split=1):
        """Estimate NELSSA sparse decode attention latency (ns).

        Models the two operational modes of the NELSSA PNM compute unit
        (SK hynix, IEEE CAL 2025) for a single decode request whose KV cache
        holds ``L`` tokens:

          M2 (sparse attention): attention GEMV over only the top-k selected
             tokens, ``k = ceil(selection_ratio * L)``. This reuses the same
             bandwidth-bound linear model as full attention but streams ``k``
             KV tokens instead of ``L``, carrying the fixed pipeline/setup
             intercept once.
          M1 (token selection): IVF vector search over the KV index. Following
             the paper's sqrt(N) heuristic (Fig. 6), ``n_list = round(sqrt(L))``
             and the ``nprobe`` probed lists hold ``~nprobe * sqrt(L)`` key
             vectors. Selection reads keys only (no values), i.e. half the
             per-token streaming cost of full attention (factor 0.5).

        Args:
            selection_ratio: fraction of KV tokens kept by sparse attention
                (e.g. 0.02 for the paper's 2% setting).
            nprobe: number of IVF lists probed during vector search.
            channel_split: memory-channel parallelism.

        Returns:
            (latency_ns, k_selected, vectors_scanned)
        """
        slope, intercept = self._scaled_coeffs(n_head, kv_head, head_dim)
        L = max(1, int(L))
        k = min(L, max(1, math.ceil(selection_ratio * L)))
        n_list = max(1, round(math.sqrt(L)))
        vectors_scanned = min(L, nprobe * math.ceil(L / n_list))

        attn_ns = slope * k + intercept          # M2 sparse attention GEMV
        select_ns = 0.5 * slope * vectors_scanned  # M1 vector search (keys only)
        total_ns = (attn_ns + select_ns) / channel_split
        return total_ns, k, vectors_scanned

