import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import metrics
from app.core.exceptions import ConflictError
from app.models.backtest import Backtest
from app.models.strategy import Strategy
from app.models.ticker import Ticker
from app.repositories.backtest_repo import BacktestRepository
from app.repositories.market_data_repo import MarketDataRepository
from app.schemas.backtests import BacktestCreate
from app.workers.celery_app import celery_app


def _assert_replay_matches(existing: Backtest, data: BacktestCreate, ticker_id: int, idempotency_key: str) -> None:
    """Reject a reused key whose body differs from the run it would replay.

    Returning the old run for a *different* request would be worse than creating a second one: the
    caller would read results computed from parameters it never asked for. Every field that changes
    what the run computes is compared. `initial_capital`/`commission`/`slippage` are `Numeric`
    columns and come back as `Decimal`, so both sides are coerced to float before comparing.
    """
    submitted = {
        "symbol": (existing.ticker_id, ticker_id),
        "start_date": (existing.start_date, data.start_date),
        "end_date": (existing.end_date, data.end_date),
        "initial_capital": (float(existing.initial_capital), float(data.initial_capital)),
        "commission": (float(existing.commission), float(data.commission)),
        "slippage": (float(existing.slippage), float(data.slippage)),
    }
    for field, (stored, value) in submitted.items():
        if stored != value:
            raise ConflictError(
                f"Idempotency-Key '{idempotency_key}' was already used for backtest {existing.id}, which has a "
                f"different {field}. Use a new key for a different request."
            )


class BacktestService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = BacktestRepository(session)

    async def create_backtest(self, user_id: uuid.UUID, data: BacktestCreate, idempotency_key: str | None = None) -> Backtest:
        """Queue a backtest run, at most once per `idempotency_key`.

        Submitting is expensive — it occupies a Celery worker for the length of the run — and the
        endpoint answers 202 before any of that work happens, so a client retry (double click, proxy
        replay, a network error after the request was actually received) previously produced a second
        identical run. With a key, the repeat returns the original row and dispatches nothing.
        """
        # Validate strategy belongs to user. This has to happen *before* the idempotency lookup:
        # strategy_id comes from the request, so looking a key up first would let a caller probe
        # another user's strategy id and read back a run they don't own.
        stmt_strat = select(Strategy).where(Strategy.id == data.strategy_id, Strategy.user_id == user_id)
        result_strat = await self.session.execute(stmt_strat)
        strategy = result_strat.scalar_one_or_none()
        if not strategy:
            raise ValueError(f"Strategy {data.strategy_id} not found or not owned by user.")

        # Resolve ticker_id from symbol
        stmt_ticker = select(Ticker).where(Ticker.symbol == data.symbol)
        result_ticker = await self.session.execute(stmt_ticker)
        ticker = result_ticker.scalar_one_or_none()
        if not ticker:
            raise ValueError(f"Ticker {data.symbol} not found in supported universe.")

        # Read out as plain ints now: the rollback in the IntegrityError branch below expires every
        # instance in the session, and reading `strategy.id` after that point would attempt lazy IO
        # from a sync attribute access (MissingGreenlet).
        strategy_id = strategy.id
        ticker_id = ticker.id

        # Resolved before the idempotency lookup so a replay can be compared on ticker too — the
        # stored row records ticker_id, not the submitted symbol.
        if idempotency_key is not None:
            existing = await self.repo.get_by_idempotency_key(strategy_id, idempotency_key)
            if existing is not None:
                _assert_replay_matches(existing, data, ticker_id, idempotency_key)
                metrics.backtest_submissions_total.labels(outcome="replayed").inc()
                return existing

        if data.start_date >= data.end_date:
            raise ValueError("start_date must be before end_date")

        # Validate the requested window against available OHLCV coverage so a bad date
        # range fails fast with a clear 400, instead of letting the worker fail the run
        # asynchronously at its data-load step ("No market data found ...").
        market_repo = MarketDataRepository(self.session)
        coverage = await market_repo.get_ohlcv_date_range(ticker_id)
        if coverage is None:
            raise ValueError(f"No price data available for {data.symbol}. Seed market data before backtesting.")
        min_date, max_date = coverage
        if data.start_date > max_date or data.end_date < min_date:
            raise ValueError(
                f"No price data for {data.symbol} between {data.start_date} and {data.end_date}. Available range: {min_date} to {max_date}."
            )

        backtest = Backtest(
            strategy_id=strategy_id,
            ticker_id=ticker_id,
            start_date=data.start_date,
            end_date=data.end_date,
            initial_capital=data.initial_capital,
            commission=data.commission,
            slippage=data.slippage,
            status="QUEUED",
            idempotency_key=idempotency_key,
        )
        try:
            created_bt = await self.repo.create_backtest(backtest)
        except IntegrityError:
            # Two concurrent submissions with the same key: the lookup above ran before the other
            # one committed, so both reached the insert and the unique constraint rejected this one.
            # Roll back and return the row that won, which is exactly what the retry asked for.
            await self.session.rollback()
            if idempotency_key is None:
                raise
            existing = await self.repo.get_by_idempotency_key(strategy_id, idempotency_key)
            if existing is None:
                raise
            metrics.backtest_submissions_total.labels(outcome="replayed").inc()
            return existing

        metrics.backtest_submissions_total.labels(outcome="queued").inc()

        # Dispatch celery task
        task = celery_app.send_task("tasks.run_backtest", args=[created_bt.id], queue="backtest")
        created_bt.celery_task_id = task.id
        await self.session.commit()
        # commit() expires every attribute; refresh before the response model reads
        # them, otherwise serialization lazy-loads outside the greenlet (MissingGreenlet).
        await self.session.refresh(created_bt)

        return created_bt

    async def get_backtest(self, backtest_id: int, user_id: uuid.UUID) -> Backtest | None:
        """Ownership-scoped: a backtest belonging to another user reads as not-found."""
        return await self.repo.get_by_id(backtest_id, user_id=user_id)

    async def get_backtest_with_result(self, backtest_id: int, user_id: uuid.UUID) -> Backtest | None:
        return await self.repo.get_with_result(backtest_id, user_id=user_id)

    async def list_backtests(self, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[Backtest]:
        return await self.repo.list_for_user(user_id, limit=limit, offset=offset)
