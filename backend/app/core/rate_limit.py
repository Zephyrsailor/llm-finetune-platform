"""Simple in-memory rate limiting helpers."""

from collections import deque
from datetime import datetime, timedelta
from typing import Deque


class InMemoryRateLimiter:
    """Naive fixed-window limiter suitable for development/testing."""

    def __init__(self, max_attempts: int, window: timedelta):
        self._max_attempts = max_attempts
        self._window = window
        self._events: dict[str, Deque[datetime]] = {}

    def check(self, key: str) -> bool:
        """Record an attempt and return whether the caller is within limits."""
        now = datetime.utcnow()
        window_start = now - self._window
        queue = self._events.setdefault(key, deque())
        while queue and queue[0] < window_start:
            queue.popleft()
        queue.append(now)
        return len(queue) <= self._max_attempts

    def reset(self, key: str) -> None:
        """Remove previously tracked attempts for a given key."""
        self._events.pop(key, None)
