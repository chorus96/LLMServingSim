#!/usr/bin/env python3
"""NELSSA design-space (config-strategy) trade-off sweep.

Runs every long-context KV strategy the simulator models -- the PNM arms and
their host-offload / CPU baselines -- across a range of prompt lengths on the
built ASTRA-Sim backend, and lays out the trade-off the NELSSA paper argues:
*where each strategy wins and where it falls over.* The strategies differ along
four axes:

  * **compute location** -- where attention runs (GPU / PNM near-memory / CPU)
  * **KV location**      -- where the KV cache lives (GPU HBM / PNM / host DRAM)
  * **selection**        -- full attention vs dynamic sparse (2% top-k)
  * **KV transfer**      -- how much KV crosses the interconnect each step

Arms:

  | arm                 | compute | KV loc   | select | transfer      |
  |---------------------|---------|----------|--------|---------------|
  | GPU-only            | GPU     | GPU HBM  | full   | none (OOMs)   |
  | NELSSA (HC-PNM)     | PNM     | PNM 1 TB | sparse | query+result  |
  | Hermes (HC-PNM)     | PNM     | PNM 1 TB | full   | query+result  |
  | CXL-PNM (HB-PNM)    | PNM     | PNM 128G | full   | query+result  |
  | FlexGen             | GPU     | host     | full   | all KV        |
  | InfiniGen           | GPU     | host     | sparse | selected KV   |
  | RetrievalAttn-CPU   | CPU     | host     | sparse | query+result  |

Each arm is driven by its own cluster config + CLI flags (they are mutually
exclusive KV strategies, so they cannot share a single offload flag). Decode
throughput is derived from Mean TPOT, so the table reflects the decode step --
where the strategies diverge. Capacity-limited arms (GPU-only, HB-PNM) show
'X' when they OOM at long context, exactly the paper's trade-off: bandwidth or
GPU HBM is fast but capacity-bound, while the HC-PNM + sparsity keeps running.

Usage (from repo root, inside the simulator container):
  python scripts/nelssa_strategy_sweep.py \
      --lengths 3072,6144,12288 --num-requests 4 \
      --out-csv outputs/strategy_sweep.csv --out-plot outputs/strategy_sweep.png
"""
import argparse
import json
import os
import re
import subprocess
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_CFG = {
    "gpu":       "configs/cluster/single_node_single_instance.json",
    "hcpnm":     "configs/cluster/single_node_nelssa_hcpnm_instance.json",
    "hbpnm":     "configs/cluster/single_node_cxlpnm_baseline_instance.json",
    "flexgen":   "configs/cluster/single_node_flexgen_baseline_instance.json",
    "infinigen": "configs/cluster/single_node_infinigen_baseline_instance.json",
    "retrieval": "configs/cluster/single_node_retrieval_cpu_instance.json",
}

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


def _run_one(cfg_rel, dataset_rel, out_csv_rel, dtype, extra_args, timeout):
    # Paths must be repo-root-relative: the simulator chdirs to astra-sim/ and
    # resolves cluster/dataset paths with a ``../`` prefix, so absolute paths
    # (e.g. /tmp/...) break.
    cmd = [
        sys.executable, "-m", "serving",
        "--cluster-config", cfg_rel,
        "--dtype", dtype, "--block-size", "16",
        "--dataset", dataset_rel,
        "--output", out_csv_rel,
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
    # No TPOT printed / non-zero exit -> infeasible (out of memory / capacity).
    return {"status": "OOM", "tpot": None, "gen_th": None}


def _fmt_len(n):
    return f"{n // 1024}K" if n % 1024 == 0 else str(n)


def _arms(args):
    """(label, config key, extra CLI args, profile string)."""
    sr = str(args.sparse_ratio)
    return [
        ("GPU-only",           "gpu",       [],
         "GPU / GPU-HBM / full / none"),
        ("NELSSA (HC-PNM)",    "hcpnm",     ["--enable-attn-offloading",
                                             "--sparse-attention-ratio", sr],
         "PNM / PNM-1TB / sparse / query+result"),
        ("Hermes (HC-PNM)",    "hcpnm",     ["--enable-attn-offloading"],
         "PNM / PNM-1TB / full / query+result"),
        ("CXL-PNM (HB-PNM)",   "hbpnm",     ["--enable-attn-offloading"],
         "PNM / PNM-128G / full / query+result"),
        ("FlexGen",            "flexgen",   ["--flexgen-host-offload"],
         "GPU / host / full / all-KV"),
        ("InfiniGen",          "infinigen", ["--infinigen-prefetch-ratio", sr],
         "GPU / host / sparse / selected-KV"),
        ("RetrievalAttn-CPU",  "retrieval", ["--enable-attn-offloading",
                                             "--sparse-attention-ratio", sr,
                                             "--retrieval-cpu-sparse"],
         "CPU / host / sparse / query+result"),
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lengths", default="3072,6144,12288",
                    help="comma-separated prompt lengths to sweep")
    ap.add_argument("--num-requests", type=int, default=4,
                    help="concurrent requests per length (batch stresses decode attention)")
    ap.add_argument("--output-tokens", type=int, default=48)
    ap.add_argument("--sparse-ratio", type=float, default=0.02)
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--timeout", type=int, default=1800, help="per-run timeout (s)")
    ap.add_argument("--only", default=None,
                    help="comma-separated arm labels to restrict the sweep to")
    ap.add_argument("--out-csv", default="outputs/strategy_sweep.csv")
    ap.add_argument("--out-plot", default=None, help="optional PNG path")
    args = ap.parse_args()

    lengths = [int(x) for x in args.lengths.split(",") if x.strip()]
    arms = _arms(args)
    if args.only:
        keep = {x.strip() for x in args.only.split(",")}
        arms = [a for a in arms if a[0] in keep]
        if not arms:
            ap.error(f"--only matched no arms; valid: {[a[0] for a in _arms(args)]}")

    tmp_rel = os.path.join("outputs", "_strategy_tmp")
    os.makedirs(os.path.join(_REPO_ROOT, tmp_rel), exist_ok=True)
    out_csv_rel = os.path.join(tmp_rel, "_run.csv")
    results = {}  # (label, length) -> dict
    try:
        for length in lengths:
            ds_rel = os.path.join(tmp_rel, f"wl_{length}.jsonl")
            _write_workload(os.path.join(_REPO_ROOT, ds_rel), length,
                            args.num_requests, args.output_tokens)
            for label, cfg_key, extra, _profile in arms:
                cfg_rel = _CFG[cfg_key]
                print(f"[run] {label:20} L={length} ...", flush=True)
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

    # NELSSA is the reference arm for relative decode throughput.
    norm_label = "NELSSA (HC-PNM)"
    have_norm = any(a[0] == norm_label for a in arms)

    def rel_of(label, length):
        if not have_norm:
            return None
        base = results.get((norm_label, length))
        r = results[(label, length)]
        if not base or r["status"] != "OK" or base["status"] != "OK" or not r["tpot"]:
            return None
        return base["tpot"] / r["tpot"]  # throughput ratio = TPOT_nelssa / TPOT_arm

    # ---- CSV -----------------------------------------------------------------
    csv_path = os.path.join(_REPO_ROOT, args.out_csv)
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    with open(csv_path, "w") as f:
        f.write("arm,profile,length,status,tpot_ms,gen_tok_s,rel_decode_throughput_vs_nelssa\n")
        for label, _, _, profile in arms:
            for length in lengths:
                r = results[(label, length)]
                rel = rel_of(label, length)
                f.write(f"{label},{profile},{length},{r['status']},{r['tpot'] or ''},"
                        f"{r['gen_th'] or ''},{('%.3f' % rel) if rel else ''}\n")

    # ---- strategy profile table ---------------------------------------------
    print("\n" + "=" * 78)
    print("NELSSA strategy trade-off -- compute / KV-location / selection / KV-transfer")
    print("=" * 78)
    print(f"{'arm':<20}{'compute':<7} {'KV loc':<9} {'select':<7} {'KV transfer'}")
    print("-" * 78)
    for label, _, _, profile in arms:
        comp, kvloc, sel, xfer = [s.strip() for s in profile.split("/")]
        print(f"{label:<20}{comp:<7} {kvloc:<9} {sel:<7} {xfer}")

    # ---- absolute TPOT table -------------------------------------------------
    hdr = "  ".join(f"{_fmt_len(l):>8}" for l in lengths)
    print("\n" + "=" * 78)
    print("Mean TPOT per step (ms) -- lower is better;  X = OOM / capacity-bound")
    print("=" * 78)
    print(f"{'arm':<20}{hdr}")
    for label, _, _, _ in arms:
        cells = []
        for length in lengths:
            r = results[(label, length)]
            if r["status"] == "OOM":
                cells.append("X")
            elif r["status"] == "TIMEOUT":
                cells.append("T/O")
            else:
                cells.append(f"{r['tpot']:.2f}")
        print(f"{label:<20}" + "  ".join(f"{c:>8}" for c in cells))

    # ---- relative decode throughput (vs NELSSA) ------------------------------
    if have_norm:
        print("\n" + "=" * 78)
        print(f"Relative decode throughput (vs {norm_label});  higher is better")
        print("=" * 78)
        print(f"{'arm':<20}{hdr}")
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
            print(f"{label:<20}" + "  ".join(f"{c:>8}" for c in cells))
    print("=" * 78)
    print(f"CSV: {csv_path}")

    if args.out_plot:
        _plot(results, arms, lengths, os.path.join(_REPO_ROOT, args.out_plot))


def _plot(results, arms, lengths, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[plot] matplotlib not available, skipping plot")
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    for label, _, _, _ in arms:
        xs, ys, oom_x = [], [], []
        for length in lengths:
            r = results[(label, length)]
            if r["status"] == "OK" and r["tpot"]:
                xs.append(length); ys.append(r["tpot"])
            elif r["status"] != "OK":
                oom_x.append(length)
        if xs:
            line, = ax.plot(xs, ys, marker="o", label=label)
            for ox in oom_x:
                ax.scatter([ox], [max(ys) if ys else 1], marker="x", s=80,
                           color=line.get_color(), zorder=5)
    ax.set_xscale("log", base=2)
    ax.set_xticks(lengths)
    ax.set_xticklabels([_fmt_len(l) for l in lengths])
    ax.set_xlabel("prompt length (tokens)")
    ax.set_ylabel("Mean TPOT per step (ms) -- lower is better")
    ax.set_title("NELSSA strategy trade-off (x = OOM / capacity-bound)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    print(f"Plot: {path}")


if __name__ == "__main__":
    main()
