"""Redis-backed fixed-window rate limiting.

Used by `RateLimitMiddleware` (wired in `app/main.py`) to cap how often a single caller can hit
expensive endpoints. Redis — not in-process memory — is the counter store because the API runs as
multiple Uvicorn workers on Render, and a per-process counter would let N workers serve N times the
configured limit.

Failure policy is **fail-open**: if Redis is unreachable the request is allowed through. A rate
limiter is a cost guard, not an authorization boundary, so a Redis outage must not take the API down
with it. The `/ready` probe already reports Redis health, so the outage stays visible.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import redis.asyncio as redis
import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RateLimitRule:
    """`limit` requests allowed per `window_seconds` for one caller on one route group."""

    name: str
    limit: int
    window_seconds: int


@dataclass(frozen=True)
class RateLimitVerdict:
    allowed: bool
    limit: int
    remaining: int
    #: Seconds until the current window expires — the value for `Retry-After` / `X-RateLimit-Reset`.
    reset_after: int


class RateLimiter:
    """Fixed-window counter over Redis.

    A fixed window (rather than a sliding log) keeps this to one `INCR` plus a conditional `EXPIRE`
    per request, and the burst it permits at a window boundary — up to 2x the limit across two
    adjacent windows — is acceptable for the abuse and cost control this is meant to provide.
    """

    def __init__(self, redis_url: str, *, key_prefix: str = "ratelimit") -> None:
        self._redis_url = redis_url
        self._key_prefix = key_prefix
        self._client: redis.Redis | None = None

    def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def check(self, rule: RateLimitRule, identity: str, *, now: float | None = None) -> RateLimitVerdict:
        """Count this request against `rule` for `identity` and report whether it is allowed."""
        current = time.time() if now is None else now
        window_start = int(current // rule.window_seconds) * rule.window_seconds
        reset_after = max(1, int(window_start + rule.window_seconds - current))
        key = f"{self._key_prefix}:{rule.name}:{identity}:{window_start}"

        try:
            client = self._get_client()
            pipe = client.pipeline()
            pipe.incr(key)
            # Expire is set on every request rather than only the first: a crash between INCR and
            # EXPIRE would otherwise leave a key with no TTL, permanently blocking that caller.
            pipe.expire(key, rule.window_seconds)
            count = int((await pipe.execute())[0])
        except Exception as exc:
            # Fail open — see module docstring.
            logger.warning("rate_limit_unavailable", rule=rule.name, error=str(exc))
            return RateLimitVerdict(allowed=True, limit=rule.limit, remaining=rule.limit, reset_after=reset_after)

        return RateLimitVerdict(
            allowed=count <= rule.limit,
            limit=rule.limit,
            remaining=max(0, rule.limit - count),
            reset_after=reset_after,
        )
