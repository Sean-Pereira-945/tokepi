"""FastAPI dependencies for request throttling and project API-key auth."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any

from fastapi import Depends, Header, HTTPException, Request

import os
from .config import get_rate_limit
from .service import DriftGuardService

REDIS_URL = os.environ.get("REDIS_URL")
if REDIS_URL:
    try:
        import redis
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    except ImportError:
        redis_client = None
else:
    redis_client = None


# ---------------------------------------------------------------------------
# Rate limiter — sliding-window in-memory counter keyed by client IP
# ---------------------------------------------------------------------------

class _SlidingWindowCounter:
    """Thread-safe sliding-window rate limiter bucket."""

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        """Initialize a counter with a request limit and rolling time window."""
        self.limit = limit
        self.window = window_seconds
        # map of ip → deque of request timestamps
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, key: str) -> bool:
        """Record a request and report whether the key remains within its limit."""
        now = time.monotonic()
        cutoff = now - self.window
        dq = self._hits[key]

        # Evict old timestamps outside the window
        while dq and dq[0] < cutoff:
            dq.popleft()

        if len(dq) >= self.limit:
            return False

        dq.append(now)
        return True

    def remaining(self, key: str) -> int:
        """Return the number of requests still available for a key."""
        now = time.monotonic()
        cutoff = now - self.window
        dq = self._hits[key]
        while dq and dq[0] < cutoff:
            dq.popleft()
        return max(0, self.limit - len(dq))


_default_limiter = _SlidingWindowCounter(limit=get_rate_limit(), window_seconds=60)
_ingestion_limiter = _SlidingWindowCounter(limit=120, window_seconds=60)


def _redis_is_allowed(key_prefix: str, key: str, limit: int, window: int) -> bool:
    """Uses Redis sorted sets for sliding window rate limiting."""
    if not redis_client:
        return True
    
    redis_key = f"rate_limit:{key_prefix}:{key}"
    now = time.monotonic()
    cutoff = now - window
    
    pipeline = redis_client.pipeline()
    pipeline.zremrangebyscore(redis_key, 0, cutoff)
    pipeline.zadd(redis_key, {str(now): now})
    pipeline.zcard(redis_key)
    pipeline.expire(redis_key, window)
    
    results = pipeline.execute()
    current_count = results[2]
    
    return current_count <= limit


def _client_key(request: Request) -> str:
    """Extract the connecting client address used as the limiter key."""
    return request.client.host if request.client else "unknown"


def rate_limit_default(request: Request) -> None:
    """FastAPI dependency — enforces the default API rate limit."""
    key = _client_key(request)
    
    if redis_client:
        allowed = _redis_is_allowed("default", key, get_rate_limit(), 60)
    else:
        allowed = _default_limiter.is_allowed(key)
        
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please slow down.",
            headers={"Retry-After": "60"},
        )


def rate_limit_ingestion(request: Request) -> None:
    """FastAPI dependency — enforces the tighter event ingestion rate limit (120/min)."""
    key = _client_key(request)
    
    if redis_client:
        allowed = _redis_is_allowed("ingestion", key, 120, 60)
    else:
        allowed = _ingestion_limiter.is_allowed(key)
        
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Ingestion rate limit exceeded.",
            headers={"Retry-After": "60"},
        )


# ---------------------------------------------------------------------------
# API key auth — for SDK → backend event ingestion calls
# ---------------------------------------------------------------------------

def build_api_key_dependency(service: DriftGuardService):
    """Returns a FastAPI dependency that validates X-API-Key and returns the project_id."""

    def require_valid_api_key(x_api_key: str | None = Header(default=None)) -> str:
        """Validate the request key and return its owning project identifier."""
        if x_api_key is None:
            raise HTTPException(status_code=401, detail="Missing X-API-Key header")
        try:
            project = service.get_project_by_api_key(x_api_key)
            return project.project_id
        except KeyError as exc:
            raise HTTPException(status_code=401, detail="Invalid API key") from exc

    return require_valid_api_key
