import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.strategy import Strategy


class StrategyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, strategy: Strategy) -> Strategy:
        self.session.add(strategy)
        await self.session.commit()
        await self.session.refresh(strategy)
        return strategy

    async def get_by_id(self, strategy_id: int, user_id: uuid.UUID) -> Strategy | None:
        stmt = select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str, user_id: uuid.UUID) -> Strategy | None:
        stmt = select(Strategy).where(Strategy.name == name, Strategy.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Strategy]:
        stmt = select(Strategy).where(Strategy.user_id == user_id).order_by(Strategy.id.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
