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


@router.get(
    "/tickers",
    response_model=list[TickerResponse],
    summary="List available tickers",
    description="Tickers that have been ingested at least once, so this is what the rest of the market-data and "
    "indicator endpoints can actually answer for. The symbol universe itself is fixed in code "
    "(`TICKER_UNIVERSE`); a symbol appears here only after an ingest created its row.",
)
async def list_tickers(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    service = MarketDataService(session)
    return await service.list_tickers()


@router.get(
    "/{symbol}",
    response_model=MarketDataResponse,
    summary="Get stored OHLCV bars",
    description="Daily bars for one symbol between `start` and `end`, both inclusive, read from Postgres — this never "
    "calls yfinance. A window with no stored data returns `count: 0` rather than an error; use "
    "`POST /market-data/{symbol}/ingest` to fill it.",
    responses={404: {"description": "Symbol has never been ingested, so no ticker row exists"}},
)
async def get_market_data(
    symbol: str,
    start: datetime.date = Query(..., description="Start date (inclusive)"),
    end: datetime.date = Query(..., description="End date (inclusive)"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
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
    summary="Ingest bars from yfinance",
    description="Fetches daily bars from yfinance and upserts them, returning `rows_upserted`. Synchronous — it "
    "returns once the write is done.\n\n"
    "Safe to re-run over an overlapping window: the upsert is `ON CONFLICT DO UPDATE` on (ticker, date), so "
    "re-ingesting corrects existing rows instead of duplicating them. The symbol must be in the fixed "
    "universe, and rows failing the adapter's sanity checks (NaN, `high < low`, negative volume) are dropped "
    "rather than stored. Rate limited to 10 requests per minute per caller, since it calls a third party.",
    responses={
        400: {"description": "Symbol outside the fixed universe, or `start` is not before `end`"},
        429: {"description": "Rate limit exceeded — see `Retry-After`"},
        502: {"description": "yfinance request failed"},
    },
)
async def ingest_market_data(
    symbol: str,
    start: datetime.date = Query(..., description="Start date (inclusive)"),
    end: datetime.date = Query(..., description="End date (exclusive, as yfinance treats it)"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    service = MarketDataService(session)
    count = await service.ingest_ticker(symbol, start, end)
    return {"message": "Ingestion complete", "rows_upserted": count}
