"""Tests for the Redis fixed-window rate limiter and its middleware.

Redis is faked rather than reached over the network: the limiter's contract is the arithmetic of the
window (when a caller crosses the limit, what `remaining`/`reset_after` report, what happens when the
store is down), and a real Redis would make those assertions depend on wall-clock timing.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.middleware.rate_limit import RateLimitMiddleware
from app.core.rate_limit import RateLimiter, RateLimitRule
from app.core.security import create_access_token


class _FakePipeline:
    """Records the commands the limiter queues and replays them against `_FakeRedis`."""

    def __init__(self, store: dict[str, int]) -> None:
        self._store = store
        self._ops: list[tuple[str, str]] = []

    def incr(self, key: str) -> None:
        self._ops.append(("incr", key))

    def expire(self, key: str, _seconds: int) -> None:
        self._ops.append(("expire", key))

    async def execute(self) -> list[int]:
        results = []
        for op, key in self._ops:
            if op == "incr":
                self._store[key] = self._store.get(key, 0) + 1
                results.append(self._store[key])
            else:
                results.append(1)
        self._ops.clear()
        return results


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self.store)


class _BrokenRedis:
    def pipeline(self):
        raise ConnectionError("redis is down")


def _limiter(client) -> RateLimiter:
    limiter = RateLimiter("redis://unused")
    limiter._client = client
    return limiter


RULE = RateLimitRule("test", limit=3, window_seconds=60)


async def test_allows_up_to_the_limit_then_blocks():
    limiter = _limiter(_FakeRedis())

    verdicts = [await limiter.check(RULE, "user:a", now=1_000.0) for _ in range(4)]

    assert [v.allowed for v in verdicts] == [True, True, True, False]
    assert [v.remaining for v in verdicts] == [2, 1, 0, 0]


async def test_identities_have_separate_budgets():
    limiter = _limiter(_FakeRedis())

    for _ in range(3):
        await limiter.check(RULE, "user:a", now=1_000.0)

    # `a` is exhausted; `b` must be untouched by that.
    assert (await limiter.check(RULE, "user:a", now=1_000.0)).allowed is False
    assert (await limiter.check(RULE, "user:b", now=1_000.0)).allowed is True


async def test_new_window_resets_the_count():
    limiter = _limiter(_FakeRedis())

    for _ in range(4):
        await limiter.check(RULE, "user:a", now=1_000.0)
    assert (await limiter.check(RULE, "user:a", now=1_000.0)).allowed is False

    # 1000 // 60 == 16 -> window starts at 960 and ends at 1020.
    assert (await limiter.check(RULE, "user:a", now=1_020.0)).allowed is True


async def test_reset_after_counts_down_to_the_window_boundary():
    limiter = _limiter(_FakeRedis())

    # Window [960, 1020): 19s left at t=1001, and never reported as 0 at the very last moment.
    assert (await limiter.check(RULE, "user:a", now=1_001.0)).reset_after == 19
    assert (await limiter.check(RULE, "user:a", now=1_019.5)).reset_after == 1


async def test_fails_open_when_redis_is_unavailable():
    limiter = _limiter(_BrokenRedis())

    # A rate limiter is a cost guard, not an authorization boundary: a Redis outage must not 429
    # every caller. Ten requests against a limit of 3 all pass.
    verdicts = [await limiter.check(RULE, "user:a", now=1_000.0) for _ in range(10)]

    assert all(v.allowed for v in verdicts)
    assert all(v.remaining == RULE.limit for v in verdicts)


def _app(limiter: RateLimiter) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        limiter=limiter,
        rules=[(r"^POST$", r"^/limited$", RULE)],
    )

    @app.post("/limited")
    async def limited():
        return {"ok": True}

    @app.post("/unlimited")
    async def unlimited():
        return {"ok": True}

    return app


@pytest.fixture
async def limited_client():
    limiter = _limiter(_FakeRedis())
    async with AsyncClient(transport=ASGITransport(app=_app(limiter)), base_url="http://test") as c:
        yield c


async def test_middleware_returns_429_with_the_standard_error_envelope(limited_client: AsyncClient):
    for _ in range(3):
        assert (await limited_client.post("/limited")).status_code == 200

    response = await limited_client.post("/limited")

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert int(response.headers["Retry-After"]) > 0


async def test_middleware_adds_headers_to_allowed_responses(limited_client: AsyncClient):
    response = await limited_client.post("/limited")

    assert response.headers["X-RateLimit-Limit"] == "3"
    assert response.headers["X-RateLimit-Remaining"] == "2"


async def test_unmatched_routes_are_not_limited(limited_client: AsyncClient):
    for _ in range(10):
        response = await limited_client.post("/unlimited")
        assert response.status_code == 200

    # No rule matched, so the limiter was never consulted and no headers were added.
    assert "X-RateLimit-Limit" not in response.headers


async def test_matching_is_method_specific(limited_client: AsyncClient):
    # The rule is POST-only; a GET to the same path must fall through (405 here, but unlimited).
    for _ in range(10):
        assert (await limited_client.get("/limited")).status_code == 405


async def test_bearer_token_identity_beats_shared_ip():
    """Two users behind one IP must not share a budget."""
    limiter = _limiter(_FakeRedis())
    headers_a = {"Authorization": f"Bearer {create_access_token('11111111-1111-1111-1111-111111111111')}"}
    headers_b = {"Authorization": f"Bearer {create_access_token('22222222-2222-2222-2222-222222222222')}"}

    async with AsyncClient(transport=ASGITransport(app=_app(limiter)), base_url="http://test") as c:
        for _ in range(3):
            assert (await c.post("/limited", headers=headers_a)).status_code == 200
        assert (await c.post("/limited", headers=headers_a)).status_code == 429
        assert (await c.post("/limited", headers=headers_b)).status_code == 200


async def test_unparseable_token_falls_back_to_ip_identity():
    limiter = _limiter(_FakeRedis())
    headers = {"Authorization": "Bearer not-a-jwt"}

    async with AsyncClient(transport=ASGITransport(app=_app(limiter)), base_url="http://test") as c:
        for _ in range(3):
            assert (await c.post("/limited", headers=headers)).status_code == 200
        # Still limited — a forged token degrades to the IP bucket rather than escaping the limit.
        assert (await c.post("/limited", headers=headers)).status_code == 429


async def test_default_rules_cover_the_expensive_endpoints():
    """Guards against a route rename silently disabling its limit."""
    from app.api.middleware.rate_limit import DEFAULT_RULES

    middleware = RateLimitMiddleware.__new__(RateLimitMiddleware)
    import re

    middleware._rules = [(re.compile(m), re.compile(p), rule) for m, p, rule in DEFAULT_RULES]

    matched = {
        ("POST", "/api/v1/conversations/8d2b/messages"): "chat",
        ("POST", "/api/v1/backtests"): "backtest",
        ("POST", "/api/v1/market-data/AAPL/ingest"): "ingest",
        ("POST", "/api/v1/documents"): "upload",
        ("POST", "/api/v1/auth/login"): "auth",
        ("POST", "/api/v1/auth/register"): "auth",
    }
    for (method, path), expected in matched.items():
        rule = middleware._match(method, path)
        assert rule is not None and rule.name == expected, f"{method} {path}"

    # Reads are cheap and must stay unlimited.
    assert middleware._match("GET", "/api/v1/backtests") is None
    assert middleware._match("GET", "/api/v1/market-data/AAPL") is None
