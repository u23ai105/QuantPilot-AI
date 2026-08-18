import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.schemas.market_data import (
    MarketDataResponse,
    OHLCVBarResponse,
    TickerResponse,
)
from app.services.market_data_service import MarketDataService

router = APIRouter()


@router.get("/tickers", response_model=list[TickerResponse])
async def list_tickers(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """List all available tickers in the system."""
    service = MarketDataService(session)
    return await service.list_tickers()


@router.get("/{symbol}", response_model=MarketDataResponse)
async def get_market_data(
    symbol: str,
    start: datetime.date = Query(..., description="Start date (inclusive)"),
    end: datetime.date = Query(..., description="End date (inclusive)"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Get OHLCV bars for a specific ticker."""
    service = MarketDataService(session)
    bars = await service.get_ohlcv(symbol, start, end)

    # SQLAlchemy models convert automatically to Pydantic responses
    # but we map them explicitly to match the schema structure.
    response_bars = [
        OHLCVBarResponse(
            date=bar.date,
            open=float(bar.open),
            high=float(bar.high),
            low=float(bar.low),
            close=float(bar.close),
            volume=bar.volume,
        )
        for bar in bars
    ]
    return MarketDataResponse(
        symbol=symbol.upper(),
        count=len(response_bars),
        bars=response_bars,
    )


@router.post(
    "/{symbol}/ingest",
    status_code=status.HTTP_201_CREATED,
)
async def ingest_market_data(
    symbol: str,
    start: datetime.date = Query(..., description="Start date (inclusive)"),
    end: datetime.date = Query(..., description="End date (inclusive)"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Trigger ingestion from yfinance for a symbol."""
    service = MarketDataService(session)
    count = await service.ingest_ticker(symbol, start, end)
    return {"message": "Ingestion complete", "rows_upserted": count}
