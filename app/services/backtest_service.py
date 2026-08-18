import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backtest import Backtest
from app.models.strategy import Strategy
from app.models.ticker import Ticker
from app.repositories.backtest_repo import BacktestRepository
from app.schemas.backtests import BacktestCreate
from app.workers.celery_app import celery_app


class BacktestService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = BacktestRepository(session)

    async def create_backtest(self, user_id: uuid.UUID, data: BacktestCreate) -> Backtest:
        # Validate strategy belongs to user
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

        if data.start_date >= data.end_date:
            raise ValueError("start_date must be before end_date")

        backtest = Backtest(
            strategy_id=strategy.id,
            ticker_id=ticker.id,
            start_date=data.start_date,
            end_date=data.end_date,
            initial_capital=data.initial_capital,
            commission=data.commission,
            slippage=data.slippage,
            status="QUEUED",
        )
        created_bt = await self.repo.create_backtest(backtest)

        # Dispatch celery task
        task = celery_app.send_task("tasks.run_backtest", args=[created_bt.id], queue="backtest")
        created_bt.celery_task_id = task.id
        await self.session.commit()

        return created_bt

    async def get_backtest(self, backtest_id: int) -> Backtest | None:
        return await self.repo.get_by_id(backtest_id)

    async def get_backtest_with_result(self, backtest_id: int) -> Backtest | None:
        return await self.repo.get_with_result(backtest_id)
