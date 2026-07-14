#!/usr/bin/env python3
"""Derive an approximate profile for a target model from a measured one.

Real profiles under ``profiler/perf/`` come from vLLM layerwise profiling on
actual GPUs (see ``profiler/AGENTS.md``). When a model's real profile is not
available (e.g. no GPU large enough to boot it), this tool synthesizes a
*derived* profile by scaling a measured source-model profile with an
analytical per-layer compute/memory model.

It is NOT a substitute for real profiling: kernel latency is assumed
proportional to per-layer FLOPs (dense/attention prefill) or KV-cache bytes
(decode attention), which holds only approximately (fixed launch overhead,
tensor-core tiling, and bandwidth effects are ignored). Use it to let the
simulator *run* an unprofiled model (e.g. Llama-3.1-70B for NELSSA studies),
and replace it with a measured profile when one becomes available. Provenance
is recorded under ``derived:`` in the generated ``meta.yaml``.

Scaling (source -> target), all from the two model configs:
  dense layers   per-layer FLOPs (qkv/o/gate_up/down/embedding/norm/rotary)
  per_sequence   lm_head ~ hidden*vocab ; sampler ~ vocab
  attention      prefill rows (prefill_chunk>0): compute-bound ~ n_head
                 decode rows  (prefill_chunk==0): KV-read-bound ~ kv_head*head_dim
  skew / skew_fit  alpha is scale-invariant, so skew_fit is copied verbatim
                 and skew raw shots are scaled by the decode (memory) factor

Per-layer counts are NOT scaled: the CSVs are per-layer and the simulator
multiplies by the target config's ``num_hidden_layers`` at runtime.

Usage:
  python -m profiler.tools.derive_profile \
      --hardware RTXPRO6000 \
      --source meta-llama/Llama-3.1-8B \
      --target meta-llama/Llama-3.1-70B \
      --variant bf16
"""
import argparse
import csv
import datetime
import json
import os
import shutil

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load_model_config(model):
    path = os.path.join(_REPO_ROOT, "configs", "model", f"{model}.json")
    with open(path) as f:
        return json.load(f)


def _head_dim(c):
    return c.get("head_dim", c["hidden_size"] // c["num_attention_heads"])


def _dims(c):
    hd = _head_dim(c)
    return {
        "hidden": c["hidden_size"],
        "inter": c.get("intermediate_size", c.get("ffn_dim")),
        "q_dim": c["num_attention_heads"] * hd,
        "kv_dim": c.get("num_key_value_heads", c["num_attention_heads"]) * hd,
        "n_head": c["num_attention_heads"],
        "kv_head": c.get("num_key_value_heads", c["num_attention_heads"]),
        "head_dim": hd,
        "vocab": c["vocab_size"],
    }


def _dense_ratios(s, t):
    """Per-token FLOP ratio (target/source) for each dense/per_sequence layer."""
    r = {
        "embedding": t["hidden"] / s["hidden"],
        "layernorm": t["hidden"] / s["hidden"],
        "input_layernorm": t["hidden"] / s["hidden"],
        "post_layernorm": t["hidden"] / s["hidden"],
        "final_layernorm": t["hidden"] / s["hidden"],
        "qk_norm": (t["q_dim"] + t["kv_dim"]) / (s["q_dim"] + s["kv_dim"]),
        "rotary_emb": (t["q_dim"] + t["kv_dim"]) / (s["q_dim"] + s["kv_dim"]),
        "qkv_proj": (t["hidden"] * (t["q_dim"] + 2 * t["kv_dim"]))
        / (s["hidden"] * (s["q_dim"] + 2 * s["kv_dim"])),
        "o_proj": (t["q_dim"] * t["hidden"]) / (s["q_dim"] * s["hidden"]),
        "gate_up_proj": (t["hidden"] * t["inter"]) / (s["hidden"] * s["inter"]),
        "act_fn": t["inter"] / s["inter"],
        "down_proj": (t["inter"] * t["hidden"]) / (s["inter"] * s["hidden"]),
        # per_sequence layers
        "lm_head": (t["hidden"] * t["vocab"]) / (s["hidden"] * s["vocab"]),
        "sampler": t["vocab"] / s["vocab"],
    }
    return r


def _scale_layer_csv(src_path, dst_path, ratios, layer_col="layer"):
    with open(src_path, newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    li = header.index(layer_col)
    ti = header.index("time_us")
    missing = set()
    out = [header]
    for row in body:
        if not row:
            continue
        name = row[li]
        if name in ratios:
            row = list(row)
            row[ti] = f"{float(row[ti]) * ratios[name]:.6g}"
        else:
            missing.add(name)
        out.append(row)
    with open(dst_path, "w", newline="") as f:
        csv.writer(f).writerows(out)
    return missing


def _scale_attention_csv(src_path, dst_path, compute_ratio, memory_ratio):
    with open(src_path, newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    pci = header.index("prefill_chunk")
    ti = header.index("time_us")
    out = [header]
    for row in body:
        if not row:
            continue
        row = list(row)
        pc = int(row[pci])
        factor = compute_ratio if pc > 0 else memory_ratio
        row[ti] = f"{float(row[ti]) * factor:.6g}"
        out.append(row)
    with open(dst_path, "w", newline="") as f:
        csv.writer(f).writerows(out)


def _scale_skew_csv(src_path, dst_path, memory_ratio):
    """Scale the raw t_*_us columns by the decode (memory) factor; alpha is
    scale-invariant and left untouched."""
    with open(src_path, newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    cols = [header.index(c) for c in ("t_mean_us", "t_max_us", "t_skew_us")]
    out = [header]
    for row in body:
        if not row:
            continue
        row = list(row)
        for ci in cols:
            row[ci] = f"{float(row[ci]) * memory_ratio:.6g}"
        out.append(row)
    with open(dst_path, "w", newline="") as f:
        csv.writer(f).writerows(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hardware", required=True)
    ap.add_argument("--source", required=True, help="source model, e.g. meta-llama/Llama-3.1-8B")
    ap.add_argument("--target", required=True, help="target model, e.g. meta-llama/Llama-3.1-70B")
    ap.add_argument("--variant", default="bf16")
    ap.add_argument("--force", action="store_true", help="overwrite an existing target profile")
    args = ap.parse_args()

    perf_root = os.path.join(_REPO_ROOT, "profiler", "perf", args.hardware)
    src_dir = os.path.join(perf_root, args.source, args.variant)
    dst_dir = os.path.join(perf_root, args.target, args.variant)
    if not os.path.isdir(src_dir):
        raise SystemExit(f"source profile not found: {src_dir}")
    if os.path.isdir(dst_dir) and not args.force:
        raise SystemExit(f"target exists (use --force): {dst_dir}")

    sc = _dims(_load_model_config(args.source))
    tc = _dims(_load_model_config(args.target))
    ratios = _dense_ratios(sc, tc)
    compute_ratio = tc["n_head"] / sc["n_head"]                       # prefill attention
    memory_ratio = (tc["kv_head"] * tc["head_dim"]) / (sc["kv_head"] * sc["head_dim"])  # decode attention

    os.makedirs(dst_dir, exist_ok=True)
    tp_dirs = sorted(d for d in os.listdir(src_dir)
                     if d.startswith("tp") and os.path.isdir(os.path.join(src_dir, d)))
    all_missing = set()
    for tp in tp_dirs:
        s_tp, d_tp = os.path.join(src_dir, tp), os.path.join(dst_dir, tp)
        os.makedirs(d_tp, exist_ok=True)
        for fname, kind in (("dense.csv", "dense"), ("per_sequence.csv", "per_sequence"),
                            ("attention.csv", "attention"), ("skew.csv", "skew"),
                            ("skew_fit.csv", "copy"), ("moe.csv", "copy")):
            sp = os.path.join(s_tp, fname)
            if not os.path.isfile(sp):
                continue
            dp = os.path.join(d_tp, fname)
            if kind in ("dense", "per_sequence"):
                all_missing |= _scale_layer_csv(sp, dp, ratios)
            elif kind == "attention":
                _scale_attention_csv(sp, dp, compute_ratio, memory_ratio)
            elif kind == "skew":
                _scale_skew_csv(sp, dp, memory_ratio)
            else:  # copy (skew_fit alphas are scale-invariant; moe passthrough)
                shutil.copyfile(sp, dp)
        print(f"[{tp}] scaled dense/per_sequence/attention, copied skew_fit")

    # meta.yaml: start from source, mark derived provenance
    if yaml is None:
        raise SystemExit("pyyaml required to write meta.yaml")
    with open(os.path.join(src_dir, "meta.yaml")) as f:
        meta = yaml.safe_load(f)
    meta["model"] = args.target
    meta["derived"] = {
        "from": args.source,
        "method": "analytical per-layer FLOP/byte scaling (NOT measured)",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "attention_prefill_factor": round(compute_ratio, 6),
        "attention_decode_factor": round(memory_ratio, 6),
        "dense_layer_factors": {k: round(v, 6) for k, v in ratios.items()},
        "note": "skew_fit alphas copied verbatim (scale-invariant); per-layer "
                "counts scaled by the target config's num_hidden_layers at runtime.",
    }
    with open(os.path.join(dst_dir, "meta.yaml"), "w") as f:
        yaml.safe_dump(meta, f, sort_keys=False)

    if all_missing:
        print(f"WARNING: no scaling ratio for layers {sorted(all_missing)} (left as-is)")
    print(f"Derived profile written to {dst_dir}")
    print(f"  attention prefill x{compute_ratio:.3f}, decode x{memory_ratio:.3f}")


if __name__ == "__main__":
    main()
