import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.backtest import Backtest, BacktestResult
from app.models.strategy import Strategy


class BacktestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_backtest(self, backtest: Backtest) -> Backtest:
        self.session.add(backtest)
        await self.session.commit()
        await self.session.refresh(backtest)
        return backtest

    async def get_by_id(self, backtest_id: int, user_id: uuid.UUID | None = None) -> Backtest | None:
        """Fetch a backtest. When user_id is given, only return it if the owning strategy belongs
        to that user (backtest ids are sequential, so unfiltered lookups are enumerable)."""
        stmt = select(Backtest).where(Backtest.id == backtest_id)
        if user_id is not None:
            stmt = stmt.join(Strategy, Backtest.strategy_id == Strategy.id).where(Strategy.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_result(self, backtest_id: int, user_id: uuid.UUID | None = None) -> Backtest | None:
        stmt = select(Backtest).options(selectinload(Backtest.result), selectinload(Backtest.strategy)).where(Backtest.id == backtest_id)
        if user_id is not None:
            stmt = stmt.join(Strategy, Backtest.strategy_id == Strategy.id).where(Strategy.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[Backtest]:
        """Newest-first backtests owned by this user."""
        stmt = (
            select(Backtest)
            .options(selectinload(Backtest.result), selectinload(Backtest.strategy))
            .join(Strategy, Backtest.strategy_id == Strategy.id)
            .where(Strategy.user_id == user_id)
            .order_by(Backtest.created_at.desc(), Backtest.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def claim_execution(self, backtest_id: int) -> bool:
        """
        Atomically update status QUEUED -> RUNNING.
        Returns True if successful, False if already claimed.
        """
        stmt = update(Backtest).where(Backtest.id == backtest_id, Backtest.status == "QUEUED").values(status="RUNNING")
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount == 1

    async def update_status(self, backtest_id: int, status: str, error_message: str | None = None) -> None:
        stmt = update(Backtest).where(Backtest.id == backtest_id).values(status=status, error_message=error_message)
        await self.session.execute(stmt)
        await self.session.commit()

    async def save_result(self, backtest_id: int, result: BacktestResult) -> None:
        """Saves result and updates status to COMPLETED atomically."""
        result.backtest_id = backtest_id
        self.session.add(result)

        stmt = update(Backtest).where(Backtest.id == backtest_id).values(status="COMPLETED")
        await self.session.execute(stmt)
        await self.session.commit()
