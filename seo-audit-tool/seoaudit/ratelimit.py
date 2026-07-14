"""Polite, thread-safe rate limiting.

A token-bucket-ish limiter that spaces requests to at most ``rps`` per second
and adds random jitter so the tool never hammers a host in a tight, machine-gun
cadence. Shared across worker threads.
"""

from __future__ import annotations

import random
import threading
import time


class RateLimiter:
    def __init__(self, rps: float, jitter: float = 0.0) -> None:
        self._min_interval = 1.0 / rps if rps > 0 else 0.0
        self._jitter = max(0.0, jitter)
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def acquire(self) -> None:
        """Block until the caller is allowed to make its next request."""
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            interval = self._min_interval
            if self._jitter and interval:
                interval += random.uniform(0, interval * self._jitter)
            self._next_allowed = now + interval
