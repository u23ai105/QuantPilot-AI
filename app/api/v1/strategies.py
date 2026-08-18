import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db_session
from app.domain.strategy_validator import ValidationError
from app.models.user import User
from app.schemas.strategies import StrategyCreate, StrategyResponse
from app.services.strategy_service import StrategyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategies", tags=["Strategies"])


@router.post(
    "",
    response_model=StrategyResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "Strategy with this name already exists"},
        422: {"description": "Invalid strategy JSON schema"},
    },
)
async def create_strategy(
    data: StrategyCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = StrategyService(session)
    try:
        strategy = await service.create_strategy(current_user.id, data)
        return strategy
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Strategy name already exists.")
    except Exception:
        logger.exception("Error creating strategy")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get(
    "",
    response_model=list[StrategyResponse],
)
async def list_strategies(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = StrategyService(session)
    strategies = await service.list_strategies(current_user.id)
    return strategies


@router.get(
    "/{strategy_id}",
    response_model=StrategyResponse,
    responses={404: {"description": "Strategy not found"}},
)
async def get_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = StrategyService(session)
    strategy = await service.get_strategy(strategy_id, current_user.id)
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    return strategy
