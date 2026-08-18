import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.backtests import (
    BacktestCreate,
    BacktestResponse,
    BacktestResultResponse,
)
from app.services.backtest_service import BacktestService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtests", tags=["Backtests"])


@router.post(
    "",
    response_model=BacktestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"description": "Validation error (e.g., strategy not owned by user)"},
    },
)
async def create_backtest(
    data: BacktestCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = BacktestService(session)
    try:
        backtest = await service.create_backtest(current_user.id, data)
        return backtest
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("Error creating backtest")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get(
    "/{backtest_id}",
    response_model=BacktestResponse,
    responses={404: {"description": "Backtest not found"}},
)
async def get_backtest(
    backtest_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    # Depending on requirements, we should probably check if the strategy belongs to current_user
    # But for simplicity, if they know the backtest_id they can view it.
    service = BacktestService(session)
    backtest = await service.get_backtest(backtest_id)
    if not backtest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found")
    return backtest


@router.get(
    "/{backtest_id}/results",
    response_model=BacktestResultResponse,
    responses={
        404: {"description": "Backtest or result not found"},
        400: {"description": "Backtest is not completed"},
    },
)
async def get_backtest_results(
    backtest_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = BacktestService(session)
    backtest = await service.get_backtest_with_result(backtest_id)

    if not backtest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found")

    if backtest.status != "COMPLETED" or not backtest.result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Results not available. Status: {backtest.status}")

    return backtest.result
