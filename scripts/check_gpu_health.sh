#!/usr/bin/env bash

# Checks basic GPU availability inside the container/host.
# Usage: ./scripts/check_gpu_health.sh

set -euo pipefail

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "[error] nvidia-smi not found. Ensure NVIDIA drivers and container toolkit are installed." >&2
  exit 1
fi

echo "[info] GPU statistics:"
nvidia-smi --query-gpu=name,memory.total,memory.used,temperature.gpu --format=csv

python_cmd=${PYTHON_BIN:-python}

cat <<'PY' | "${python_cmd}" -
import torch

if not torch.cuda.is_available():
    raise SystemExit("CUDA unavailable or no GPU visible to PyTorch")

print(f"CUDA OK, device count: {torch.cuda.device_count()}")
for idx in range(torch.cuda.device_count()):
    name = torch.cuda.get_device_name(idx)
    capability = torch.cuda.get_device_capability(idx)
    print(f"  - GPU {idx}: {name}, capability={capability}")
PY
