---
sidebar_position: 7
title: Derived profiles & replacing them
---

# Derived profiles & replacing them

Some profiles under `profiler/perf/` are **derived**, not measured: they
are produced by analytically scaling a measured profile of a *different*
model on the same hardware, rather than by running the vLLM profiler on
the target model. This is a stopgap for models you cannot profile yet
(e.g. a 70B model with no GPU large enough on hand), so the simulator can
still run the architecture.

Derived profiles are approximate by construction — kernel launch overhead,
tensor-core tiling, and bandwidth effects are not captured — so replace
them with a measured profile whenever you can.

## Spotting a derived profile

Two markers:

1. A `README.md` in the model's perf folder
   (`profiler/perf/<HW>/<MODEL>/README.md`) saying it is derived.
2. A `derived:` block in `meta.yaml`:

```yaml title="profiler/perf/RTXPRO6000/meta-llama/Llama-3.1-70B/bf16/meta.yaml"
derived:
  from: meta-llama/Llama-3.1-8B
  method: analytical per-layer FLOP/byte scaling (NOT measured)
  attention_prefill_factor: 2.0
  attention_decode_factor: 1.0
  dense_layer_factors: { o_proj: 4.0, qkv_proj: 3.333, act_fn: 2.0, ... }
```

A measured profile has **no** `derived:` block. That is exactly how you
confirm a replacement succeeded.

## Path A — measure the real profile (preferred)

This overwrites the derived bundle in place: same
`perf/<HW>/<MODEL>/<variant>/` path, so no simulator or config change is
needed afterward.

### 1. Provision hardware that fits the model

The profiler emulates each TP degree on a **single GPU** by dividing the
per-rank shapes (`hidden_size`, `num_attention_heads`, …) by TP via
`hf_overrides`, so it does not need a full multi-GPU box — but the
per-rank shard plus its activations must fit in one GPU's memory. For a
70B model at `bf16`, profile the TP degrees you will actually run
(e.g. `TP_DEGREES="2,4,8"`); each degree is booted with weights loaded as
`dummy` so you do not need the real checkpoint, only enough VRAM for the
sharded shapes.

:::tip Profile every runtime TP
The simulator looks up `tp<N>/` for the instance's `tp_size`. If your
cluster config runs `tp_size=4`, the profile **must** contain a `tp4/`
folder, or the run fails with a missing-variant error. Always include `1`
in `TP_DEGREES`; `tp_stable` layers are profiled once there and replicated.
:::

### 2. Launch the vLLM container

```bash
./scripts/docker-vllm.sh
```

Set `HF_TOKEN` in `scripts/docker-vllm.sh` so the gated config downloads on
first run. See **[Running](./running)** for the full container walkthrough.

### 3. Point `profile.sh` at the model and force a clean run

Edit `profiler/profile.sh`:

```bash
MODEL="meta-llama/Llama-3.1-70B"   # same id as the derived profile
HARDWARE="RTXPRO6000"              # same hardware label → same perf/ path
TP_DEGREES="2,4,8"                 # cover every tp_size you will simulate
FORCE=1                            # wipe the derived CSVs and re-profile from scratch
```

`FORCE=1` is important: without it the profiler resumes and preloads the
existing (derived) CSV rows. Then run:

```bash
./profiler/profile.sh
```

The writer emits fresh `dense.csv`, `per_sequence.csv`, `attention.csv`,
`skew.csv`, `skew_fit.csv` and a `meta.yaml` **without** a `derived:` block.
Delete the now-stale `README.md` marker:

```bash
rm profiler/perf/RTXPRO6000/meta-llama/Llama-3.1-70B/README.md
```

### 4. Verify

```bash
# the derived: block should be gone
grep -c "^derived:" profiler/perf/RTXPRO6000/meta-llama/Llama-3.1-70B/bf16/meta.yaml   # -> 0

# re-run the scenario you cared about and compare to the derived numbers
python -m serving \
  --cluster-config 'configs/cluster/single_node_nelssa_70b_instance.json' \
  --dtype bfloat16 --enable-attn-offloading --sparse-attention-ratio 0.02 \
  --dataset 'workloads/example_trace.jsonl' --output 'outputs/nelssa_70b.csv'
```

Large TTFT/TPOT shifts vs the derived run are expected and are the whole
point — the measured profile captures kernel behavior the FLOP-scaling
model could not.

## Path B — re-derive (still no GPU)

If you cannot measure yet but want a better approximation — a different
source model, hardware, or variant — re-run the derivation tool. It
regenerates the `derived:` provenance each time:

```bash
python profiler/tools/derive_profile.py \
  --hardware RTXPRO6000 \
  --source meta-llama/Llama-3.1-8B \
  --target meta-llama/Llama-3.1-70B \
  --variant bf16 \
  --force
```

Choose a `--source` whose architecture is as close to the target as
possible (same `model_type`, similar GQA ratio and `head_dim`) so the
per-layer scaling stays honest. The tool scales dense layers by GEMM
FLOPs, `lm_head`/`sampler` by `hidden×vocab` / `vocab`, and attention
piecewise (prefill by `num_attention_heads`, decode by
`num_key_value_heads × head_dim`); `skew_fit` alphas are copied verbatim
because they are scale-invariant. Per-layer counts are **not** scaled —
the simulator multiplies by the target config's `num_hidden_layers` at
runtime.

## Checklist

- [ ] `TP_DEGREES` covers every `tp_size` your cluster configs use.
- [ ] `FORCE=1` set, so derived rows are wiped, not resumed.
- [ ] `meta.yaml` has no `derived:` block after a real profile run.
- [ ] The `README.md` derived-marker is removed.
- [ ] A simulator run reproduces and the numbers look sane.

## See also

- **[Running](./running)** — the full profiler run walkthrough.
- **[Output bundle](./output-bundle)** — the CSV/`meta.yaml` contract the
  simulator consumes.
- **[NELSSA sparse attention](/docs/examples/disaggregated/nelssa-sparse-attention)**
  — the study that ships the derived Llama-70B profile.
