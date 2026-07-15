#!/bin/bash
# Bare-metal install helper for the LLMServingSim simulator (ASTRA-Sim backend).
#
# The simulator normally runs inside the sim Docker container
# (see docker-sim.sh, image astrasim/tutorial-micro2024). This script sets up
# the equivalent on bare metal: it initializes the ASTRA-Sim submodule,
# installs the C++ build toolchain and the Python deps, builds ASTRA-Sim +
# Chakra (via compile.sh), and aligns the protobuf runtime with Chakra's
# generated code.
#
# Run from anywhere; paths resolve to the repo root. Installing system
# packages (step 1) needs root — run with sudo/as root, or pre-install
# cmake, g++, make, protobuf-compiler and libprotobuf-dev yourself.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # .../scripts
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"                    # .../LLMServingSim
cd "$REPO_ROOT"

# ---------------------------------------------------------------------------
# 1. System build toolchain (C++ compiler, CMake, protobuf compiler+headers).
# ---------------------------------------------------------------------------
NEED_PKGS=()
command -v cmake  >/dev/null 2>&1 || NEED_PKGS+=(cmake)
command -v g++    >/dev/null 2>&1 || NEED_PKGS+=(g++)
command -v make   >/dev/null 2>&1 || NEED_PKGS+=(make)
command -v protoc >/dev/null 2>&1 || NEED_PKGS+=(protobuf-compiler)
ls /usr/include/google/protobuf/*.h >/dev/null 2>&1 || NEED_PKGS+=(libprotobuf-dev)

if [ ${#NEED_PKGS[@]} -gt 0 ]; then
  echo "[install-sim] installing system packages: ${NEED_PKGS[*]}"
  SUDO=""; [ "$(id -u)" -eq 0 ] || SUDO="sudo"
  if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get update -qq
    $SUDO apt-get install -y "${NEED_PKGS[@]}"
  else
    echo "[install-sim] ERROR: missing ${NEED_PKGS[*]} and apt-get not found." >&2
    echo "               Install them with your package manager, then re-run." >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# 2. ASTRA-Sim submodule (+ nested: chakra, fmt, spdlog, yaml-cpp, ...).
# ---------------------------------------------------------------------------
echo "[install-sim] initializing ASTRA-Sim submodule ..."
git submodule update --init --recursive astra-sim

# ---------------------------------------------------------------------------
# 3. Python runtime deps. Mirrors docker-sim.sh (plus rich, used by the
#    logger). Left unpinned: docker-sim.sh pins numpy/pandas/matplotlib for
#    the container's older Python, but those pins fail to build on current
#    Python — pip resolves compatible versions here.
# ---------------------------------------------------------------------------
echo "[install-sim] installing Python deps ..."
PIP="pip3"; command -v pip3 >/dev/null 2>&1 || PIP="python3 -m pip"
$PIP install rich pyyaml pyinstrument transformers datasets \
  msgspec scikit-learn xgboost matplotlib pandas numpy

# ---------------------------------------------------------------------------
# 4. Build ASTRA-Sim (analytical backend) + install the Chakra converter.
# ---------------------------------------------------------------------------
echo "[install-sim] building ASTRA-Sim + Chakra ..."
bash "$SCRIPT_DIR/compile.sh"

# ---------------------------------------------------------------------------
# 5. Chakra ships et_def_pb2.py generated with protobuf >= 7.35 but pins
#    protobuf==6.* in its metadata, so a fresh install leaves an older runtime
#    that refuses to load the generated code. Align it (only if the import
#    currently fails).
# ---------------------------------------------------------------------------
if ! python3 -c "from chakra.schema.protobuf import et_def_pb2" >/dev/null 2>&1; then
  echo "[install-sim] aligning protobuf runtime with Chakra gencode ..."
  $PIP install "protobuf==7.35.1"
fi

# ---------------------------------------------------------------------------
# 6. Sanity checks.
# ---------------------------------------------------------------------------
python3 -c "from chakra.schema.protobuf import et_def_pb2; print('[install-sim] Chakra protobuf OK')"
BIN="$REPO_ROOT/astra-sim/build/astra_analytical/build/AnalyticalAstra/bin/AnalyticalAstra"
if [ -e "$BIN" ]; then
  echo "[install-sim] ASTRA-Sim binary: $BIN"
  echo "[install-sim] Done. Try a run from the repo root:"
  echo "  python -m serving --cluster-config configs/cluster/single_node_single_instance.json \\"
  echo "    --dtype bfloat16 --dataset workloads/example_trace.jsonl --output outputs/run.csv"
else
  echo "[install-sim] ERROR: ASTRA-Sim binary not found at $BIN" >&2
  exit 1
fi
