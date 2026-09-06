"""Redis-backed JSON cache.

One shared client, created lazily, for cached values that are cheap to store and expensive to
recompute. The first user is the RAG query-embedding cache (`app/ai/embedding_cache.py`), where a miss
costs a call against the Gemini embedding quota.

Failure policy is **fail-open**, the same as the rate limiter: a Redis outage turns every lookup into a
miss and every write into a no-op, so the caller falls back to computing the value. A cache is a cost
optimization, not a correctness mechanism, and `/ready` already reports Redis health.

The client is a module singleton rather than per-request: `redis.from_url` builds a connection pool, and
constructing one per request would open and discard pools under load. `close_cache()` disposes it from
the app's lifespan.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class RedisJSONCache:
    """`get`/`set` of JSON-serializable values, namespaced by `key_prefix`, with a required TTL.

    Every write carries a TTL: nothing stored here is authoritative, so an entry that outlives its
    usefulness should disappear on its own rather than occupy Redis until someone notices.
    """

    def __init__(self, redis_url: str, *, key_prefix: str = "cache") -> None:
        self._redis_url = redis_url
        self._key_prefix = key_prefix
        self._client: redis.Redis | None = None

    def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    def _namespaced(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        """The decoded value, or `None` for a miss, unreachable Redis, or an undecodable entry."""
        try:
            raw = await self._get_client().get(self._namespaced(key))
        except Exception as exc:
            logger.warning("cache_unavailable", operation="get", error=str(exc))
            return None

        if raw is None:
            return None

        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            # Treated as a miss rather than an error: a value written by an older, incompatible version
            # of the code should degrade into a recompute, not a 500.
            logger.warning("cache_value_undecodable", key=key)
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            await self._get_client().set(self._namespaced(key), json.dumps(value), ex=ttl_seconds)
        except Exception as exc:
            logger.warning("cache_unavailable", operation="set", error=str(exc))

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


_cache: RedisJSONCache | None = None


def get_cache() -> RedisJSONCache:
    """The process-wide cache instance."""
    global _cache
    if _cache is None:
        _cache = RedisJSONCache(settings.redis_url, key_prefix="cache")
    return _cache


async def close_cache() -> None:
    """Dispose the shared client. Called from the app lifespan on shutdown."""
    global _cache
    if _cache is not None:
        await _cache.close()
        _cache = None
