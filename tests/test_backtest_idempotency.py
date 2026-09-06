"""Idempotency-Key handling on POST /api/v1/backtests.

Submission is a 202 that queues a Celery job, so a client retry used to produce a second identical
run. These tests pin the three behaviours that matter: a repeated key returns the original row and
dispatches nothing, a key reused with a different body is a 409, and no key at all still creates a
new run every time.

Celery is stubbed out (`send_task`) — the point is what the API does, not what the worker does.
"""

from datetime import date
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.backtest import Backtest
from app.models.ohlcv import OHLCV
from app.models.strategy import Strategy
from app.models.ticker import Ticker
from app.services import backtest_service

_RULES = {
    "version": 1,
    "entry": {"logic": "AND", "conditions": [{"indicator": "rsi", "params": {"period": 14}, "operator": "lt", "against": 30}]},
    "exit": {"logic": "AND", "conditions": [{"indicator": "rsi", "params": {"period": 14}, "operator": "gt", "against": 70}]},
    "position_sizing": {"type": "fixed_fraction", "value": 0.5},
}

_BODY = {
    "strategy_id": None,  # filled per test
    "symbol": "IDMP",
    "start_date": "2025-01-02",
    "end_date": "2025-01-10",
    "initial_capital": 10000,
}


@pytest.fixture
def stub_celery(monkeypatch):
    """Replace `send_task` with a call recorder, so dispatch count is directly observable."""
    calls = []

    def fake_send_task(name, args=None, queue=None, **kwargs):
        calls.append((name, tuple(args or ()), queue))
        return SimpleNamespace(id=f"task-{len(calls)}")

    monkeypatch.setattr(backtest_service.celery_app, "send_task", fake_send_task)
    return calls


@pytest.fixture
async def submittable(db_session, test_user):
    """A strategy owned by `test_user` plus a ticker with OHLCV covering the request window.

    `create_backtest` validates the window against stored coverage, so bars are required or every
    submission 400s before reaching the idempotency logic.

    Ids are returned in a plain namespace because each `commit()` expires every ORM instance in the
    session — including `test_user` — and re-reading an expired attribute from a sync context raises
    MissingGreenlet.
    """
    user_id = test_user.id

    ticker = Ticker(symbol="IDMP", name="Idempotency Test Corp")
    db_session.add(ticker)
    await db_session.commit()
    await db_session.refresh(ticker)
    ticker_id = ticker.id

    db_session.add_all(
        [OHLCV(ticker_id=ticker_id, date=date(2025, 1, day), open=100, high=101, low=99, close=100, volume=1_000) for day in (2, 3, 6, 7, 8, 9, 10)]
    )
    strategy = Strategy(user_id=user_id, name="Idempotency probe", rules_json=_RULES, version=1)
    db_session.add(strategy)
    await db_session.commit()
    await db_session.refresh(strategy)

    return SimpleNamespace(strategy_id=strategy.id, ticker_id=ticker_id, user_id=user_id)


def _body(submittable, **overrides):
    return {**_BODY, "strategy_id": submittable.strategy_id, **overrides}


async def _count_backtests(db_session) -> int:
    return (await db_session.execute(select(func.count()).select_from(Backtest))).scalar_one()


async def test_repeat_key_returns_same_run_without_requeueing(client: AsyncClient, test_user_token: str, submittable, stub_celery, db_session):
    headers = {"Authorization": f"Bearer {test_user_token}", "Idempotency-Key": "retry-me"}

    first = await client.post("/api/v1/backtests", json=_body(submittable), headers=headers)
    second = await client.post("/api/v1/backtests", json=_body(submittable), headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["id"] == first.json()["id"]
    # The point of the feature: one row, one Celery dispatch.
    assert await _count_backtests(db_session) == 1
    assert len(stub_celery) == 1


async def test_no_key_creates_a_new_run_each_time(client: AsyncClient, test_user_token: str, submittable, stub_celery, db_session):
    """Omitting the header must not become an implicit dedupe — the old behaviour is preserved."""
    headers = {"Authorization": f"Bearer {test_user_token}"}

    first = await client.post("/api/v1/backtests", json=_body(submittable), headers=headers)
    second = await client.post("/api/v1/backtests", json=_body(submittable), headers=headers)

    assert first.status_code == second.status_code == 202
    assert first.json()["id"] != second.json()["id"]
    assert await _count_backtests(db_session) == 2
    assert len(stub_celery) == 2


async def test_different_keys_create_different_runs(client: AsyncClient, test_user_token: str, submittable, stub_celery, db_session):
    auth = {"Authorization": f"Bearer {test_user_token}"}

    first = await client.post("/api/v1/backtests", json=_body(submittable), headers={**auth, "Idempotency-Key": "key-a"})
    second = await client.post("/api/v1/backtests", json=_body(submittable), headers={**auth, "Idempotency-Key": "key-b"})

    assert first.json()["id"] != second.json()["id"]
    assert await _count_backtests(db_session) == 2
    assert len(stub_celery) == 2


@pytest.mark.parametrize(
    "override",
    [
        {"start_date": "2025-01-03"},
        {"end_date": "2025-01-09"},
        {"initial_capital": 25000},
        {"commission": 0.005},
        {"slippage": 0.002},
    ],
)
async def test_reused_key_with_different_body_conflicts(client: AsyncClient, test_user_token: str, submittable, stub_celery, override):
    """Answering a *different* request with the old run would hand back results the caller never asked for."""
    headers = {"Authorization": f"Bearer {test_user_token}", "Idempotency-Key": "same-key"}

    first = await client.post("/api/v1/backtests", json=_body(submittable), headers=headers)
    assert first.status_code == 202

    second = await client.post("/api/v1/backtests", json=_body(submittable, **override), headers=headers)

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CONFLICT"
    # Nothing extra was queued by the rejected replay.
    assert len(stub_celery) == 1


async def test_reused_key_with_different_symbol_conflicts(client: AsyncClient, test_user_token: str, submittable, db_session, stub_celery):
    """The stored row records ticker_id, so the symbol comparison has to resolve the ticker first."""
    db_session.add(Ticker(symbol="IDMP2", name="Other Idempotency Corp"))
    await db_session.commit()
    other = (await db_session.execute(select(Ticker).where(Ticker.symbol == "IDMP2"))).scalar_one()
    db_session.add_all(
        [OHLCV(ticker_id=other.id, date=date(2025, 1, day), open=50, high=51, low=49, close=50, volume=500) for day in (2, 3, 6, 7, 8, 9, 10)]
    )
    await db_session.commit()

    headers = {"Authorization": f"Bearer {test_user_token}", "Idempotency-Key": "symbol-key"}
    await client.post("/api/v1/backtests", json=_body(submittable), headers=headers)

    second = await client.post("/api/v1/backtests", json=_body(submittable, symbol="IDMP2"), headers=headers)

    assert second.status_code == 409
    assert "symbol" in second.json()["error"]["message"]
    assert len(stub_celery) == 1


async def test_key_is_persisted_on_the_row(client: AsyncClient, test_user_token: str, submittable, stub_celery, db_session):
    headers = {"Authorization": f"Bearer {test_user_token}", "Idempotency-Key": "stored-key"}

    response = await client.post("/api/v1/backtests", json=_body(submittable), headers=headers)

    stored = (await db_session.execute(select(Backtest).where(Backtest.id == response.json()["id"]))).scalar_one()
    assert stored.idempotency_key == "stored-key"


async def test_key_from_another_users_strategy_is_not_reachable(client: AsyncClient, test_user_token: str, submittable, stub_celery, db_session):
    """Ownership is checked before the key lookup, so a foreign strategy_id 400s rather than leaking a run."""
    from app.core.security import get_password_hash
    from app.models.user import User

    stranger = User(email="idmp-stranger@example.com", hashed_password=get_password_hash("password123"))
    db_session.add(stranger)
    await db_session.commit()
    await db_session.refresh(stranger)
    foreign = Strategy(user_id=stranger.id, name="Not yours", rules_json=_RULES, version=1)
    db_session.add(foreign)
    await db_session.commit()
    await db_session.refresh(foreign)
    foreign_id = foreign.id

    headers = {"Authorization": f"Bearer {test_user_token}", "Idempotency-Key": "probe"}
    response = await client.post("/api/v1/backtests", json=_body(submittable, strategy_id=foreign_id), headers=headers)

    assert response.status_code == 400
    assert len(stub_celery) == 0


async def test_same_key_on_a_different_strategy_is_independent(client: AsyncClient, test_user_token: str, submittable, stub_celery, db_session):
    """The unique constraint is (strategy_id, idempotency_key) — one caller's key per strategy."""
    second_strategy = Strategy(user_id=submittable.user_id, name="Second", rules_json=_RULES, version=1)
    db_session.add(second_strategy)
    await db_session.commit()
    await db_session.refresh(second_strategy)
    # Captured now: the first POST commits, which expires this instance.
    second_strategy_id = second_strategy.id

    headers = {"Authorization": f"Bearer {test_user_token}", "Idempotency-Key": "shared"}
    first = await client.post("/api/v1/backtests", json=_body(submittable), headers=headers)
    second = await client.post("/api/v1/backtests", json=_body(submittable, strategy_id=second_strategy_id), headers=headers)

    assert first.status_code == second.status_code == 202
    assert first.json()["id"] != second.json()["id"]
    assert len(stub_celery) == 2


async def test_concurrent_insert_losing_the_race_returns_the_winner(db_session, submittable, stub_celery):
    """The check-then-insert is not atomic; the unique constraint is what actually enforces this.

    The interleaving that matters: our lookup finds nothing, another worker commits its row, and our
    INSERT then violates `uq_backtests_strategy_idempotency_key`. Reproduced by planting the winning
    row up front and making only the *first* lookup report "not found" — the same state the service
    would see in a real race, without needing a second connection.
    """
    from app.schemas.backtests import BacktestCreate

    winner = Backtest(
        strategy_id=submittable.strategy_id,
        ticker_id=submittable.ticker_id,
        start_date=date(2025, 1, 2),
        end_date=date(2025, 1, 10),
        initial_capital=10000,
        commission=0.001,
        slippage=0.0,
        status="QUEUED",
        idempotency_key="raced",
    )
    db_session.add(winner)
    await db_session.commit()
    await db_session.refresh(winner)
    winner_id = winner.id

    service = backtest_service.BacktestService(db_session)
    original_lookup = service.repo.get_by_idempotency_key
    calls = []

    async def lookup_blind_on_first_call(strategy_id, key):
        calls.append(key)
        if len(calls) == 1:
            return None
        return await original_lookup(strategy_id, key)

    service.repo.get_by_idempotency_key = lookup_blind_on_first_call

    result = await service.create_backtest(
        submittable.user_id,
        BacktestCreate(strategy_id=submittable.strategy_id, symbol="IDMP", start_date=date(2025, 1, 2), end_date=date(2025, 1, 10)),
        idempotency_key="raced",
    )

    # The loser returns the winner's row rather than a duplicate...
    assert result.id == winner_id
    assert len(calls) == 2  # pre-insert lookup, then the post-IntegrityError re-read
    # ...and must not queue a run for a row it did not create.
    assert len(stub_celery) == 0
