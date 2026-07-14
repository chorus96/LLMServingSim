# Llama-3.1-70B (derived profile)

**This profile is derived, not measured.** It was produced by analytically
scaling the measured `meta-llama/Llama-3.1-8B` profile on the same hardware
(`RTXPRO6000`) with a per-layer FLOP/byte model, using:

```bash
python profiler/tools/derive_profile.py --hardware RTXPRO6000 \
  --source meta-llama/Llama-3.1-8B --target meta-llama/Llama-3.1-70B --variant bf16
```

See the `derived:` block in `bf16/meta.yaml` for the exact scaling factors.
Kernel launch overhead, tensor-core tiling, and bandwidth effects are not
modeled, so absolute latencies are approximate. It lets the simulator run
the 70B architecture (e.g. for NELSSA studies) until a measured profile is
available; replace it by re-running the vLLM profiler on real hardware.
