from datetime import date
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, get_password_hash
from app.models.backtest import Backtest, BacktestResult
from app.models.strategy import Strategy
from app.models.ticker import Ticker
from app.models.user import User

_RULES = {
    "version": 1,
    "entry": {"logic": "AND", "conditions": [{"indicator": "rsi", "params": {"period": 14}, "operator": "lt", "against": 30}]},
    "exit": {"logic": "AND", "conditions": [{"indicator": "rsi", "params": {"period": 14}, "operator": "gt", "against": 70}]},
    "position_sizing": {"type": "fixed_fraction", "value": 0.5},
}


@pytest.fixture
async def other_users_backtest(db_session):
    """A COMPLETED backtest owned by somebody other than `test_user`.

    Ids are copied into a plain namespace because every commit below expires the ORM
    instances, and re-reading an expired attribute outside the async greenlet raises
    MissingGreenlet.
    """
    other = User(email="stranger@example.com", hashed_password=get_password_hash("password123"))
    ticker = Ticker(symbol="ZZZZ", name="Test Corp")
    db_session.add_all([other, ticker])
    await db_session.commit()
    await db_session.refresh(other)
    await db_session.refresh(ticker)
    owner_id, ticker_id = other.id, ticker.id

    strategy = Strategy(user_id=owner_id, name="Stranger's edge", rules_json=_RULES, version=1)
    db_session.add(strategy)
    await db_session.commit()
    await db_session.refresh(strategy)
    strategy_id = strategy.id

    backtest = Backtest(
        strategy_id=strategy_id,
        ticker_id=ticker_id,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 6, 1),
        initial_capital=10000,
        commission=0.001,
        slippage=0.0,
        status="COMPLETED",
    )
    db_session.add(backtest)
    await db_session.commit()
    await db_session.refresh(backtest)
    backtest_id = backtest.id

    db_session.add(
        BacktestResult(
            backtest_id=backtest_id,
            total_return=0.1,
            cagr=0.1,
            volatility=0.2,
            sharpe_ratio=0.5,
            sortino_ratio=0.6,
            max_drawdown=0.05,
            win_rate=0.5,
            total_trades=4,
            equity_curve_json=[{"date": "2025-01-02T00:00:00", "value": 10000.0}],
            trades_json=[{"pnl": 100.0}],
        )
    )
    await db_session.commit()

    return SimpleNamespace(id=backtest_id, strategy_id=strategy_id, owner_id=owner_id)


async def test_get_backtest_cross_user_denied(client: AsyncClient, test_user_token: str, other_users_backtest):
    """Backtest ids are sequential, so an unscoped read would let anyone enumerate other users' runs."""
    headers = {"Authorization": f"Bearer {test_user_token}"}

    response = await client.get(f"/api/v1/backtests/{other_users_backtest.id}", headers=headers)

    assert response.status_code == 404


async def test_get_backtest_results_cross_user_denied(client: AsyncClient, test_user_token: str, other_users_backtest):
    headers = {"Authorization": f"Bearer {test_user_token}"}

    response = await client.get(f"/api/v1/backtests/{other_users_backtest.id}/results", headers=headers)

    assert response.status_code == 404


async def test_owner_can_read_own_backtest(client: AsyncClient, other_users_backtest):
    """Same row, fetched by its real owner, must still be readable — the guard scopes, it doesn't block."""
    headers = {"Authorization": f"Bearer {create_access_token(str(other_users_backtest.owner_id))}"}

    response = await client.get(f"/api/v1/backtests/{other_users_backtest.id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == other_users_backtest.id

    results = await client.get(f"/api/v1/backtests/{other_users_backtest.id}/results", headers=headers)
    assert results.status_code == 200
    assert results.json()["total_trades"] == 4


async def test_list_backtests_only_returns_own(client: AsyncClient, test_user_token: str, other_users_backtest):
    headers = {"Authorization": f"Bearer {test_user_token}"}

    response = await client.get("/api/v1/backtests", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_list_backtests_returns_owners_run(client: AsyncClient, other_users_backtest):
    headers = {"Authorization": f"Bearer {create_access_token(str(other_users_backtest.owner_id))}"}

    response = await client.get("/api/v1/backtests", headers=headers)

    assert response.status_code == 200
    assert [b["id"] for b in response.json()] == [other_users_backtest.id]


async def test_list_backtests_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/backtests")

    assert response.status_code == 401
