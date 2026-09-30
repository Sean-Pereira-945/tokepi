"""Sliding-window rate limiting, in memory or shared through Redis."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Protocol

logger = logging.getLogger(__name__)


class RateLimiter(Protocol):
    def allow(self, key: str, limit: int, window_seconds: float = 60.0) -> bool:
        """Record a hit for ``key`` and report whether it is within ``limit``."""


class MemoryRateLimiter:
    """Per-process sliding-window limiter. Use Redis when running several workers."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# Atomic check-and-add so concurrent workers cannot overshoot the limit.
_REDIS_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
if redis.call('ZCARD', key) >= limit then
  return 0
end
redis.call('ZADD', key, now, ARGV[4])
redis.call('PEXPIRE', key, math.ceil(window * 1000))
return 1
"""


class RedisRateLimiter:
    """Sliding-window limiter shared by every worker through Redis.

    Uses wall-clock time so all workers agree on the window. If Redis is
    unreachable the request is allowed and a warning is logged.
    """

    def __init__(self, url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(url)
        self._script = self._client.register_script(_REDIS_SCRIPT)

    def allow(self, key: str, limit: int, window_seconds: float = 60.0) -> bool:
        try:
            return bool(
                self._script(
                    keys=[f"driftguard:ratelimit:{key}"], args=[time.time(), window_seconds, limit, uuid.uuid4().hex]
                )
            )
        except Exception as exc:
            logger.warning("Redis rate limiter unavailable, allowing request: %s", exc)
            return True


def build_rate_limiter(redis_url: str | None) -> RateLimiter:
    """Use Redis when configured, otherwise an in-process limiter."""
    if redis_url:
        try:
            return RedisRateLimiter(redis_url)
        except ImportError:
            logger.warning("REDIS_URL is set but the redis package is missing; using in-memory rate limiting")
    return MemoryRateLimiter()
