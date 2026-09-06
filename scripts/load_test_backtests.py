"""Load test for `POST /api/v1/backtests` — submission latency only.

**Scope: the submission path, nothing else.** The endpoint answers 202 as soon as the row is committed
and the Celery job is dispatched, so what this measures is the synchronous work: auth, strategy
ownership lookup, ticker resolution, the OHLCV coverage check, the INSERT, and the broker publish. It
deliberately does *not* wait for runs to finish, and it never touches the chat or RAG endpoints — those
spend LLM quota, which is a hard external limit, not a throughput question.

Two things to know before running it:

1. **Rate limiting will dominate.** `DEFAULT_RULES` allows 10 submissions per minute per caller, so a
   load test against a normally-configured API measures the rate limiter, not the endpoint. Start the
   API with `RATE_LIMIT_ENABLED=false` for a meaningful number. The script reports the 429 count either
   way, so a run against a limited API is obvious rather than silently wrong.
2. **Every 202 is a real queued run.** With a worker attached they will all execute. Rows are tagged
   with a per-run `Idempotency-Key` prefix so `--cleanup` can delete exactly the ones this script
   created, and nothing else.

Usage::

    python -m scripts.load_test_backtests --requests 200 --concurrency 20
    python -m scripts.load_test_backtests --requests 200 --concurrency 20 --cleanup

Percentiles come from the measured samples — nothing here is estimated.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from collections import Counter
from dataclasses import dataclass

import httpx
from sqlalchemy import delete, func, select

from app.core.db import async_session_maker
from app.models.backtest import Backtest
from app.models.strategy import Strategy
from app.models.user import User

#: Prefix on every key this script sends, so its rows are identifiable for `--cleanup`.
KEY_PREFIX = "loadtest"


@dataclass
class Sample:
    status: int
    seconds: float


def percentile(sorted_values: list[float], fraction: float) -> float:
    """Nearest-rank percentile of an already-sorted list.

    Nearest-rank rather than interpolated: every reported number is then an actual observed latency,
    not a value between two measurements.
    """
    if not sorted_values:
        return float("nan")
    index = min(len(sorted_values) - 1, max(0, round(fraction * len(sorted_values) + 0.5) - 1))
    return sorted_values[index]


async def resolve_target(email: str) -> tuple[int, str]:
    """A strategy id owned by `email`, plus the symbol to submit against.

    Read from the DB rather than passed in, so the script fails with a clear message when the dev
    database has not been seeded instead of producing a run of 400s that looks like a latency result.
    """
    async with async_session_maker() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            raise SystemExit(f"No user {email!r}. Register one, or pass --email for an existing account.")
        strategy = (await session.execute(select(Strategy).where(Strategy.user_id == user.id).order_by(Strategy.id).limit(1))).scalar_one_or_none()
        if strategy is None:
            raise SystemExit(f"User {email!r} owns no strategies. Create one in the UI first.")
        return strategy.id, strategy.name


async def login(client: httpx.AsyncClient, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if response.status_code != 200:
        raise SystemExit(f"Login failed ({response.status_code}): {response.text[:200]}")
    return response.json()["access_token"]


async def submit(client: httpx.AsyncClient, token: str, payload: dict, key: str) -> Sample:
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": key}
    started = time.perf_counter()
    response = await client.post("/api/v1/backtests", json=payload, headers=headers)
    return Sample(status=response.status_code, seconds=time.perf_counter() - started)


async def run_load(args: argparse.Namespace, strategy_id: int) -> list[Sample]:
    payload = {
        "strategy_id": strategy_id,
        "symbol": args.symbol,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "initial_capital": 10000,
    }
    # `limits` raised to match concurrency: httpx defaults to 10 keepalive connections, which would
    # serialize a higher concurrency and make the result a measurement of the client, not the API.
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=30.0, limits=limits) as client:
        token = await login(client, args.email, args.password)
        semaphore = asyncio.Semaphore(args.concurrency)

        async def one(index: int) -> Sample:
            async with semaphore:
                # A distinct key per request: reusing one would make every request after the first a
                # replay, which skips the insert and the dispatch and measures the wrong path.
                return await submit(client, token, payload, f"{KEY_PREFIX}-{args.run_id}-{index}")

        return await asyncio.gather(*(one(i) for i in range(args.requests)))


async def cleanup(run_id: str) -> int:
    """Delete only the rows this run created, matched on its key prefix."""
    async with async_session_maker() as session:
        pattern = f"{KEY_PREFIX}-{run_id}-%"
        count = (await session.execute(select(func.count()).select_from(Backtest).where(Backtest.idempotency_key.like(pattern)))).scalar_one()
        await session.execute(delete(Backtest).where(Backtest.idempotency_key.like(pattern)))
        await session.commit()
        return count


def report(samples: list[Sample], wall_seconds: float, args: argparse.Namespace) -> None:
    statuses = Counter(sample.status for sample in samples)
    latencies = sorted(sample.seconds for sample in samples)
    accepted = sorted(sample.seconds for sample in samples if sample.status == 202)

    print(f"\n{'=' * 68}")
    print(f"POST /api/v1/backtests — {args.requests} requests, concurrency {args.concurrency}")
    print(f"{'=' * 68}")
    print(f"wall clock        {wall_seconds:.2f}s")
    print(f"throughput        {len(samples) / wall_seconds:.1f} req/s")
    print(f"status codes      {dict(sorted(statuses.items()))}")
    if statuses.get(429):
        print("  ^ rate limited — restart the API with RATE_LIMIT_ENABLED=false for an endpoint measurement")
    print("\nlatency, all responses (s)")
    for label, fraction in (("p50", 0.50), ("p95", 0.95), ("p99", 0.99)):
        print(f"  {label}             {percentile(latencies, fraction):.4f}")
    print(f"  min             {latencies[0]:.4f}")
    print(f"  max             {latencies[-1]:.4f}")
    if accepted and len(accepted) != len(latencies):
        print("\nlatency, 202s only (s)")
        for label, fraction in (("p50", 0.50), ("p95", 0.95), ("p99", 0.99)):
            print(f"  {label}             {percentile(accepted, fraction):.4f}")
    print(f"\n{statuses.get(202, 0)} runs were queued. `--cleanup` deletes them (key prefix {KEY_PREFIX}-{args.run_id}-).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", default="ui-check@example.com")
    parser.add_argument("--password", default="password123")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--start-date", default="2024-01-02")
    parser.add_argument("--end-date", default="2024-03-01")
    parser.add_argument("--run-id", default=None, help="Tag for this run's idempotency keys; defaults to a timestamp.")
    parser.add_argument("--cleanup", action="store_true", help="Delete the rows this run created when it finishes.")
    args = parser.parse_args()
    if args.run_id is None:
        args.run_id = str(int(time.time()))
    return args


async def main() -> None:
    args = parse_args()
    strategy_id, strategy_name = await resolve_target(args.email)
    print(f"target: strategy {strategy_id} ({strategy_name!r}), symbol {args.symbol}, run-id {args.run_id}")

    started = time.perf_counter()
    samples = await run_load(args, strategy_id)
    wall_seconds = time.perf_counter() - started

    report(samples, wall_seconds, args)

    if args.cleanup:
        deleted = await cleanup(args.run_id)
        print(f"cleanup: deleted {deleted} backtest rows created by this run.")


if __name__ == "__main__":
    asyncio.run(main())
