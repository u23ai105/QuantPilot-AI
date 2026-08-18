import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.strategy_validator import StrategyValidator
from app.models.strategy import Strategy
from app.repositories.strategy_repo import StrategyRepository
from app.schemas.strategies import StrategyCreate


class StrategyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = StrategyRepository(session)
        self.validator = StrategyValidator(session)

    async def create_strategy(self, user_id: uuid.UUID, data: StrategyCreate) -> Strategy:
        # Validate rules_json
        await self.validator.validate(data.rules_json.model_dump(mode="json"))

        # Create model
        strategy = Strategy(
            user_id=user_id,
            name=data.name,
            rules_json=data.rules_json.model_dump(mode="json"),
            version=1,
        )
        return await self.repo.create(strategy)

    async def get_strategy(self, strategy_id: int, user_id: uuid.UUID) -> Strategy | None:
        return await self.repo.get_by_id(strategy_id, user_id)

    async def list_strategies(self, user_id: uuid.UUID) -> list[Strategy]:
        return await self.repo.list_for_user(user_id)
