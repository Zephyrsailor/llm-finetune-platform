"""GPU locking utilities for training tasks.

Usage:
    from scripts.gpu_lock import acquire_gpu

    with acquire_gpu(0):
        launch_training(...)

The lock is implemented via Redis. Update REDIS_URL if needed.
"""

from __future__ import annotations

import contextlib
import os
import time
from typing import Generator

from redis import Redis  # type: ignore[import]


DEFAULT_REDIS_URL = "redis://localhost:6379/0"
LOCK_KEY_TEMPLATE = "gpu-lock:{gpu_id}"
LOCK_TTL_SECONDS = int(os.getenv("GPU_LOCK_TTL", "3600"))  # 1 hour by default


def _get_redis() -> Redis:
    url = os.getenv("REDIS_URL", DEFAULT_REDIS_URL)
    return Redis.from_url(url)


@contextlib.contextmanager
def acquire_gpu(gpu_id: int, timeout_seconds: int = 30) -> Generator[int, None, None]:
    """Acquire an exclusive lock for the given GPU id.

    Args:
        gpu_id: GPU index exposed via CUDA_VISIBLE_DEVICES.
        timeout_seconds: How long to wait before giving up.

    Raises:
        TimeoutError: if the GPU remains locked beyond the timeout.
    """

    redis = _get_redis()
    key = LOCK_KEY_TEMPLATE.format(gpu_id=gpu_id)
    start = time.time()

    while time.time() - start < timeout_seconds:
        if redis.set(key, "locked", nx=True, ex=LOCK_TTL_SECONDS):
            try:
                yield gpu_id
            finally:
                redis.delete(key)
            return
        time.sleep(1.0)

    raise TimeoutError(f"GPU {gpu_id} still locked after {timeout_seconds}s")


def release_all_locks() -> None:
    """Utility to clear all gpu-lock keys (for maintenance purposes)."""
    redis = _get_redis()
    pattern = LOCK_KEY_TEMPLATE.format(gpu_id="*")
    keys = redis.keys(pattern)
    if keys:
        redis.delete(*keys)


if __name__ == "__main__":
    # Simple smoke test
    try:
        with acquire_gpu(0, timeout_seconds=1):
            print("Acquired GPU 0 lock")
    except TimeoutError as exc:
        print(f"Failed to acquire GPU lock: {exc}")
