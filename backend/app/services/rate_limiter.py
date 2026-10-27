"""
Rate limiter service for API protection.
Implements a sliding-window in-memory limiter keyed by client IP.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from fastapi import HTTPException, Request


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window rate limiter."""

    def __init__(self, max_requests: int = 15, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> None:
        """Verify if *key* has exceeded the request threshold."""
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            # Purge requests older than window_start
            timestamps = [t for t in self._requests[key] if t > window_start]
            if len(timestamps) >= self.max_requests:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Rate limit exceeded: maximum {self.max_requests} requests "
                        f"per {int(self.window_seconds)}s. Please slow down."
                    ),
                )
            timestamps.append(now)
            self._requests[key] = timestamps


# Default global rate limiter for job creation: 15 jobs per minute per client IP
job_rate_limiter = SlidingWindowRateLimiter(max_requests=15, window_seconds=60.0)


def get_client_ip(request: Request) -> str:
    """Extract client IP handling x-forwarded-for header safely."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"
