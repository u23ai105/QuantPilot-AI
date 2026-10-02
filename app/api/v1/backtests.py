import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db_session
from app.core.exceptions import QuantPilotException
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
    summary="Submit a backtest",
    description="Queues a backtest on the Celery `backtest` queue and returns 202 immediately with status "
    "`QUEUED`; poll `GET /backtests/{id}` for `RUNNING → COMPLETED|FAILED`.\n\n"
    "Send an `Idempotency-Key` header to make retries safe: a repeat with the same key returns the run the "
    "first call created instead of queueing a second one. Reusing a key with a different body is a 409.",
    responses={
        400: {"description": "Validation error (e.g., strategy not owned by user, or no price data for the window)"},
        409: {"description": "`Idempotency-Key` reused with a different request body"},
        429: {"description": "Rate limit exceeded (10 per minute per caller, since each run occupies a worker) — see `Retry-After`"},
    },
)
async def create_backtest(
    data: BacktestCreate,
    idempotency_key: str | None = Header(
        None,
        alias="Idempotency-Key",
        max_length=255,
        description="Opaque client-generated key (e.g. a UUID). Scoped to the strategy; omit it to always create a new run.",
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = BacktestService(session)
    try:
        backtest = await service.create_backtest(current_user.id, data, idempotency_key=idempotency_key)
        return backtest
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except QuantPilotException:
        # ConflictError (key reused with a different body) — let the registered handler emit the
        # `{"error": {...}}` envelope instead of collapsing it into a 500 below.
        raise
    except Exception:
        logger.exception("Error creating backtest")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get(
    "",
    response_model=list[BacktestResponse],
    summary="List your backtests",
    description="Returns the caller's backtests, newest first. Only backtests whose strategy is owned by the authenticated user are included.",
)
async def list_backtests(
    limit: int = Query(50, ge=1, le=200, description="Maximum number of backtests to return."),
    offset: int = Query(0, ge=0, description="Number of backtests to skip, for paging."),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = BacktestService(session)
    return await service.list_backtests(current_user.id, limit=limit, offset=offset)


@router.get(
    "/{backtest_id}",
    response_model=BacktestResponse,
    summary="Get a backtest",
    description="Fetch a single backtest by id, including its current status. Backtests owned by another user "
    "return 404 (not 403) so ids cannot be enumerated.",
    responses={404: {"description": "Backtest not found, or not owned by the caller"}},
)
async def get_backtest(
    backtest_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = BacktestService(session)
    # Ownership-scoped lookup: backtest ids are sequential, so an unscoped read would let any
    # authenticated user walk other users' backtests by guessing ids.
    backtest = await service.get_backtest(backtest_id, current_user.id)
    if not backtest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found")
    return backtest


@router.get(
    "/{backtest_id}/results",
    response_model=BacktestResultResponse,
    summary="Get backtest results",
    description="Performance metrics, equity curve and trade list for a COMPLETED backtest. Returns 400 while the "
    "run is still QUEUED/RUNNING, and 404 if the backtest is missing or owned by another user.",
    responses={
        404: {"description": "Backtest or result not found, or not owned by the caller"},
        400: {"description": "Backtest is not completed"},
    },
)
async def get_backtest_results(
    backtest_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    service = BacktestService(session)
    backtest = await service.get_backtest_with_result(backtest_id, current_user.id)

    if not backtest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found")

    if backtest.status != "COMPLETED" or not backtest.result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Results not available. Status: {backtest.status}")

    return backtest.result
