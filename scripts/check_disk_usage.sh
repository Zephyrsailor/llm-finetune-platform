#!/usr/bin/env bash

# Check disk usage for artefact directory and emit warning if threshold exceeded.
# Usage: ./scripts/check_disk_usage.sh [/var/lib/llmft] [THRESHOLD_PERCENT]

set -euo pipefail

BASE_DIR=${1:-/var/lib/llmft}
THRESHOLD=${2:-80}

if [ ! -d "$BASE_DIR" ]; then
  echo "[warn] directory $BASE_DIR does not exist."
  exit 0
fi

usage=$(df -P "$BASE_DIR" | tail -1 | awk '{print $5}' | tr -d '%')
echo "[info] disk usage for $BASE_DIR: ${usage}% (threshold ${THRESHOLD}%)"

if [ "$usage" -ge "$THRESHOLD" ]; then
  echo "[warn] usage ${usage}% exceeds threshold ${THRESHOLD}%." >&2
  exit 2
fi
