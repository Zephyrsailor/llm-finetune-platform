#!/usr/bin/env bash

# Clean up stale training artefacts and logs.
# Environment variables:
#   BASE_DIR: artefact root directory (default: /var/lib/llmft)
#   RETENTION_DAYS: number of days to keep logs (default: 30)
#   MODEL_KEEP: number of recent training runs/models to keep per project (default: 5)

set -euo pipefail

BASE_DIR=${BASE_DIR:-/var/lib/llmft}
RETENTION_DAYS=${RETENTION_DAYS:-30}
MODEL_KEEP=${MODEL_KEEP:-5}

if [ ! -d "$BASE_DIR" ]; then
  echo "[warn] BASE_DIR $BASE_DIR does not exist, skipping cleanup."
  exit 0
fi

echo "[cleanup] removing training logs older than ${RETENTION_DAYS} days"
find "$BASE_DIR/logs" -type f -mtime +"$RETENTION_DAYS" -print -delete 2>/dev/null || true

echo "[cleanup] pruning training runs (keeping latest ${MODEL_KEEP})"
find "$BASE_DIR/training" -type d -name "runs" -print0 2>/dev/null | while IFS= read -r -d '' runs_dir; do
  ls -1t "$runs_dir" 2>/dev/null | tail -n +$((MODEL_KEEP + 1)) | while read -r old_run; do
    target="$runs_dir/$old_run"
    echo "  removing $target"
    rm -rf "$target"
  done
done

echo "[cleanup] pruning archived models (keeping latest ${MODEL_KEEP})"
find "$BASE_DIR/models" -mindepth 3 -maxdepth 3 -type d -print0 2>/dev/null | while IFS= read -r -d '' version_dir; do
  parent=$(dirname "$version_dir")
  ls -1t "$parent" 2>/dev/null | tail -n +$((MODEL_KEEP + 1)) | while read -r old_version; do
    target="$parent/$old_version"
    echo "  removing $target"
    rm -rf "$target"
  done
done

echo "[cleanup] completed at $(date)"
