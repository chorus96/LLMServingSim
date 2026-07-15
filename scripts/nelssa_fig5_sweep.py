#!/usr/bin/env python3
"""Reproduce NELSSA's Fig. 5 throughput-vs-sequence-length comparison.

Sweeps a set of prompt lengths and, for each, runs three PNM arms on the
built ASTRA-Sim backend, then reports relative decode throughput normalised
to the Hermes (HC-PNM full-attention) baseline -- with 'X' for out-of-memory
configurations, like the paper's figure:

  * Hermes  (HC-PNM full)   -- DDR5 ~200 GB/s, high capacity   -> 1x baseline
  * NELSSA  (HC-PNM sparse)  -- same device, dynamic sparse attn -> scales up
  * CXL-PNM (HB-PNM full)   -- LPDDR5X ~1.1 TB/s, low capacity  -> fast, OOMs

Decode throughput is derived from Mean TPOT (time per output token), so it
reflects the decode step -- where the arms differ -- rather than prefill.
The KV-cache capacity is sourced from each PNM's ``mem_size`` (the simulator's
PNM KV-budget model), so a small HB-PNM OOMs on long prompts while the large
HC-PNM keeps running -- reproducing the paper's trade-off.

Notes on scale:
  * The decode-attention advantage grows with KV length, so use a batch
    (``--num-requests``) and long-enough prompts to see it.
  * A PNM's capacity override must stay >= its per-channel DIMM size (256 GB
    for the DDR5 HC-PNM, 16 GB for the LPDDR5X HB-PNM) or ``pim_channels``
    rounds to 0 and PIM is disabled. OOM therefore appears at large lengths;
    faithful multi-hundred-K/M-token sweeps are slow.

Usage (from repo root, inside the simulator container):
  python scripts/nelssa_fig5_sweep.py \
      --lengths 3072,6144,12288 --num-requests 4 \
      --out-csv outputs/fig5_sweep.csv --out-plot outputs/fig5_sweep.png
"""
import argparse
import json
import os
import re
import subprocess
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_HCPNM_CFG = "configs/cluster/single_node_nelssa_hcpnm_instance.json"
_HBPNM_CFG = "configs/cluster/single_node_cxlpnm_baseline_instance.json"

_TPOT_RE = re.compile(r"Mean TPOT \(ms\):\s*([\d.]+)")
_GEN_TH_RE = re.compile(r"Average generation throughput \(tok/s\):\s*([\d.]+)")


def _write_workload(path, length, n_requests, output_tokens, seed=0):
    import random
    rng = random.Random(seed)
    with open(path, "w") as f:
        t = 0
        for _ in range(n_requests):
            t += 5_000_000  # arrive close together -> concurrent decode batch
            row = {
                "input_toks": length,
                "output_toks": output_tokens,
                "arrival_time_ns": t,
                "input_tok_ids": [rng.randint(1, 30000) for _ in range(length)],
                "output_tok_ids": [rng.randint(1, 30000) for _ in range(output_tokens)],
            }
            f.write(json.dumps(row) + "\n")


def _write_config(base_rel, cpu_mem_gb, dst):
    with open(os.path.join(_REPO_ROOT, base_rel)) as f:
        cfg = json.load(f)
    # PNM is remote-attached (cpu_mem.pim_config); its mem_size is the KV
    # capacity. Only override when asked: the capacity must stay >= the PNM's
    # per-channel DIMM size or pim_channels rounds to 0 and PIM is disabled.
    if cpu_mem_gb is not None:
        cfg["nodes"][0]["cpu_mem"]["mem_size"] = cpu_mem_gb
    with open(dst, "w") as f:
        json.dump(cfg, f)


def _run_one(cfg_path, dataset, out_csv, dtype, extra_args, timeout):
    # Paths must be repo-root-relative: the simulator chdirs to astra-sim/ and
    # resolves cluster/dataset paths with a ``../`` prefix, so absolute paths
    # (e.g. /tmp/...) break.
    cmd = [
        sys.executable, "-m", "serving",
        "--cluster-config", cfg_path,
        "--dtype", dtype, "--block-size", "16",
        "--enable-attn-offloading",
        "--dataset", dataset,
        "--output", out_csv,
        "--log-level", "WARNING",
    ] + extra_args
    try:
        p = subprocess.run(cmd, cwd=_REPO_ROOT, capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "tpot": None, "gen_th": None}
    out = p.stdout + p.stderr
    m = _TPOT_RE.search(out)
    if p.returncode == 0 and m:
        gth = _GEN_TH_RE.search(out)
        return {"status": "OK", "tpot": float(m.group(1)),
                "gen_th": float(gth.group(1)) if gth else None}
    # No TPOT printed / non-zero exit -> infeasible (out of memory).
    return {"status": "OOM", "tpot": None, "gen_th": None}


def _fmt_len(n):
    return f"{n // 1024}K" if n % 1024 == 0 else str(n)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lengths", default="3072,6144,12288",
                    help="comma-separated prompt lengths to sweep")
    ap.add_argument("--num-requests", type=int, default=4,
                    help="concurrent requests per length (batch stresses decode attention)")
    ap.add_argument("--output-tokens", type=int, default=48)
    ap.add_argument("--sparse-ratio", type=float, default=0.02)
    ap.add_argument("--hbpnm-gb", type=int, default=None,
                    help="override HB-PNM (CXL-PNM) KV capacity GB (default: config 128; "
                    "must stay >= 16 GB DIMM or PIM disables)")
    ap.add_argument("--hcpnm-gb", type=int, default=None,
                    help="override HC-PNM (Hermes/NELSSA) KV capacity GB (default: config 1024; "
                    "must stay >= 256 GB DIMM)")
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--timeout", type=int, default=1800, help="per-run timeout (s)")
    ap.add_argument("--out-csv", default="outputs/fig5_sweep.csv")
    ap.add_argument("--out-plot", default=None, help="optional PNG path")
    args = ap.parse_args()

    lengths = [int(x) for x in args.lengths.split(",") if x.strip()]
    arms = [
        # (label, base config, cpu_mem GB override or None, extra CLI args)
        ("Hermes (HC-PNM full)",   _HCPNM_CFG, args.hcpnm_gb, []),
        ("NELSSA (HC-PNM sparse)", _HCPNM_CFG, args.hcpnm_gb,
         ["--sparse-attention-ratio", str(args.sparse_ratio)]),
        ("CXL-PNM (HB-PNM full)",  _HBPNM_CFG, args.hbpnm_gb, []),
    ]

    tmp_rel = os.path.join("outputs", "_fig5_tmp")
    os.makedirs(os.path.join(_REPO_ROOT, tmp_rel), exist_ok=True)
    out_csv_rel = os.path.join(tmp_rel, "_run.csv")
    results = {}  # (label, length) -> dict
    try:
        for length in lengths:
            ds_rel = os.path.join(tmp_rel, f"wl_{length}.jsonl")
            _write_workload(os.path.join(_REPO_ROOT, ds_rel), length,
                            args.num_requests, args.output_tokens)
            for label, base, cpu_gb, extra in arms:
                cfg_rel = os.path.join(tmp_rel, f"cfg_{label.split()[0]}_{length}.json")
                _write_config(base, cpu_gb, os.path.join(_REPO_ROOT, cfg_rel))
                print(f"[run] {label:24} L={length} ...", flush=True)
                r = _run_one(cfg_rel, ds_rel, out_csv_rel, args.dtype, extra, args.timeout)
                results[(label, length)] = r
                print(f"      -> {r['status']}"
                      + (f"  TPOT={r['tpot']:.2f} ms" if r["status"] == "OK" else ""),
                      flush=True)
    finally:
        subprocess.run(["git", "checkout", "--", "astra-sim/inputs"],
                       cwd=_REPO_ROOT, capture_output=True)
        subprocess.run(["rm", "-rf", "astra-sim/inputs/runs", tmp_rel],
                       cwd=_REPO_ROOT, capture_output=True)

    # ---- normalise to Hermes (relative decode throughput = 1/TPOT) ----------
    norm_label = arms[0][0]
    csv_path = os.path.join(_REPO_ROOT, args.out_csv)
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)

    def rel_of(label, length):
        base = results[(norm_label, length)]
        r = results[(label, length)]
        if r["status"] != "OK" or base["status"] != "OK" or not r["tpot"]:
            return None
        return base["tpot"] / r["tpot"]  # throughput ratio = TPOT_hermes/TPOT_arm

    with open(csv_path, "w") as f:
        f.write("arm,length,status,tpot_ms,gen_tok_s,rel_decode_throughput\n")
        for length in lengths:
            for label, _, _, _ in arms:
                r = results[(label, length)]
                rel = rel_of(label, length)
                f.write(f"{label},{length},{r['status']},{r['tpot'] or ''},"
                        f"{r['gen_th'] or ''},{('%.3f' % rel) if rel else ''}\n")

    print("\n" + "=" * 72)
    print("NELSSA Fig. 5 -- relative decode throughput (normalised to Hermes)")
    print("=" * 72)
    hdr = "  ".join(f"{_fmt_len(l):>8}" for l in lengths)
    print(f"{'arm':<24}{hdr}")
    for label, _, _, _ in arms:
        cells = []
        for length in lengths:
            r = results[(label, length)]
            if r["status"] == "OOM":
                cells.append("X")
            elif r["status"] == "TIMEOUT":
                cells.append("T/O")
            else:
                rel = rel_of(label, length)
                cells.append(f"{rel:.2f}x" if rel else "-")
        print(f"{label:<24}" + "  ".join(f"{c:>8}" for c in cells))
    print("=" * 72)
    print("(X = OOM / infeasible;  values are decode throughput vs Hermes)")
    print(f"CSV: {csv_path}")

    if args.out_plot:
        _plot(results, arms, lengths, rel_of, args, os.path.join(_REPO_ROOT, args.out_plot))


def _plot(results, arms, lengths, rel_of, args, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[plot] matplotlib not available, skipping plot")
        return
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for label, _, _, _ in arms:
        xs, ys, oom_x = [], [], []
        for length in lengths:
            r = results[(label, length)]
            rel = rel_of(label, length)
            if r["status"] == "OK" and rel is not None:
                xs.append(length); ys.append(rel)
            elif r["status"] != "OK":
                oom_x.append(length)
        if xs:
            ax.plot(xs, ys, marker="o", label=label)
        for ox in oom_x:
            ax.scatter([ox], [0.05], marker="x", s=90, color="red", zorder=5)
    ax.set_xscale("log", base=2)
    ax.set_xticks(lengths)
    ax.set_xticklabels([_fmt_len(l) for l in lengths])
    ax.set_xlabel("prompt length (tokens)")
    ax.set_ylabel("relative decode throughput (vs Hermes)")
    ax.set_title("NELSSA Fig. 5 reproduction (x = OOM)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    print(f"Plot: {path}")


if __name__ == "__main__":
    main()
