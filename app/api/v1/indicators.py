import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.indicators import (
    IndicatorMultiPointResponse,
    IndicatorMultiResponse,
    IndicatorPointResponse,
    IndicatorResponse,
)
from app.services.indicator_service import IndicatorService

router = APIRouter()


@router.get(
    "/{symbol}",
    response_model=IndicatorResponse | IndicatorMultiResponse,
    summary="Calculate an indicator",
    description="Computes one indicator over stored bars for `[start, end]`. Deterministic: the same inputs always "
    "give the same values, calculated by the pure functions in `app/domain/indicators.py`.\n\n"
    "Warm-up is handled for you — the service reads extra bars *before* `start` so the first returned value is "
    "already converged, rather than the artefact you would get by starting the calculation at `start`. Which "
    "parameters apply depends on the indicator; irrelevant ones are ignored, and omitted ones take the "
    "conventional default (period 20 for SMA/EMA/Bollinger, 14 for RSI/ATR, 12/26/9 for MACD, 2.0 std dev).\n\n"
    "The response shape follows the indicator: single-valued ones (`sma`, `ema`, `rsi`, `atr`) return "
    "`points[].value`, while multi-valued ones (`macd`, `bollinger`) return `points[].values` keyed by line "
    "name.",
    responses={
        400: {"description": "Unknown indicator, non-positive period, or MACD `fast` not less than `slow`"},
        404: {"description": "Symbol has never been ingested"},
    },
)
async def get_indicator(
    symbol: str,
    indicator: Literal["sma", "ema", "rsi", "macd", "bollinger", "atr"] = Query(..., description="Indicator name"),
    start: datetime.date = Query(..., description="Start date (inclusive)"),
    end: datetime.date = Query(..., description="End date (inclusive)"),
    period: int | None = Query(None, description="Lookback window for SMA, EMA, RSI, Bollinger and ATR. Ignored for MACD."),
    fast: int | None = Query(None, description="MACD fast EMA period. Must be less than `slow`."),
    slow: int | None = Query(None, description="MACD slow EMA period."),
    signal: int | None = Query(None, description="MACD signal-line EMA period."),
    std_dev: float | None = Query(None, description="Bollinger band width in standard deviations."),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    service = IndicatorService(session)

    # Collect params
    params = {}
    if period is not None:
        params["period"] = period
    if fast is not None:
        params["fast"] = fast
    if slow is not None:
        params["slow"] = slow
    if signal is not None:
        params["signal"] = signal
    if std_dev is not None:
        params["std_dev"] = std_dev

    dates, values = await service.calculate(symbol, indicator, params, start, end)

    if indicator in ("macd", "bollinger"):
        points = [IndicatorMultiPointResponse(date=d, values=v) for d, v in zip(dates, values)]
        return IndicatorMultiResponse(
            symbol=symbol.upper(),
            indicator=indicator,
            points=points,
        )
    else:
        points = [IndicatorPointResponse(date=d, value=v) for d, v in zip(dates, values)]
        return IndicatorResponse(
            symbol=symbol.upper(),
            indicator=indicator,
            points=points,
        )
