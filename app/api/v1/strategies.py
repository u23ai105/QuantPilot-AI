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
    summary="Create a strategy",
    description="Stores a declarative JSON strategy — entry/exit rules over indicators, no user code. It is validated "
    "here rather than at backtest time, so a malformed rule set is rejected while you are still editing it "
    "instead of failing later inside a worker.\n\n"
    "The rules are compiled into a `backtesting.py` strategy class when a backtest runs; every indicator "
    "referenced must be one of `sma`, `ema`, `rsi`, `macd`, `bollinger`, `atr`. Names are unique per user, so "
    'two users may both have a strategy called "RSI mean reversion".',
    responses={
        409: {"description": "You already have a strategy with this name"},
        422: {"description": "The strategy JSON failed validation — the message names the offending rule"},
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
    summary="List your strategies",
    description="Every strategy owned by the caller, with its full `rules_json`. Scoped to the authenticated user; "
    "there is no way to read another account's strategies.",
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
    summary="Get a strategy",
    description="Fetch one strategy by id. A strategy owned by another user returns 404, not 403 — ids are "
    "sequential, so a 403 would confirm which ids exist.",
    responses={404: {"description": "Strategy not found, or not owned by the caller"}},
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
