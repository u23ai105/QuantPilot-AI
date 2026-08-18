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
)
async def get_indicator(
    symbol: str,
    indicator: Literal["sma", "ema", "rsi", "macd", "bollinger", "atr"] = Query(..., description="Indicator name"),
    start: datetime.date = Query(..., description="Start date (inclusive)"),
    end: datetime.date = Query(..., description="End date (inclusive)"),
    period: int | None = Query(None, description="Period (for SMA/EMA/RSI/BB/ATR)"),
    fast: int | None = Query(None, description="MACD fast period"),
    slow: int | None = Query(None, description="MACD slow period"),
    signal: int | None = Query(None, description="MACD signal period"),
    std_dev: float | None = Query(None, description="Bollinger standard deviation"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Calculate and return indicator values."""
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
