"""Market data service — orchestrates ingestion and retrieval."""

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.infrastructure.yfinance_adapter import (
    TICKER_UNIVERSE,
    VALID_SYMBOLS,
    YFinanceAdapter,
)
from app.models.ohlcv import OHLCV
from app.models.ticker import Ticker
from app.repositories.market_data_repo import MarketDataRepository


class MarketDataService:
    def __init__(self, session: AsyncSession):
        self.repo = MarketDataRepository(session)
        self.adapter = YFinanceAdapter()

    async def ingest_ticker(
        self,
        symbol: str,
        start: datetime.date,
        end: datetime.date,
    ) -> int:
        """Fetch from yfinance and upsert into database.

        Args:
            symbol: Ticker symbol.
            start: Start date.
            end: End date.

        Returns:
            Number of rows upserted.

        Raises:
            ValidationError: If symbol is not in fixed universe.
            DataProviderError: If external provider fails.
        """
        symbol = symbol.upper()
        if symbol not in VALID_SYMBOLS:
            raise ValidationError(f"Symbol {symbol} not in fixed universe.")

        if start >= end:
            raise ValidationError("Start date must be before end date.")

        # Ensure ticker exists in DB
        ticker = await self.repo.get_ticker_by_symbol(symbol)
        if not ticker:
            # Look up name and sector from universe definition
            universe_def = next(t for t in TICKER_UNIVERSE if t["symbol"] == symbol)
            ticker = await self.repo.create_ticker(
                symbol=universe_def["symbol"],
                name=universe_def["name"],
                sector=universe_def["sector"],
            )

        # Adapter handles validation (NaN drop, high>=low, vol>=0)
        df = await self.adapter.fetch(symbol, start, end)

        if df.empty:
            return 0

        # Convert to list of dicts for repository
        rows = df.to_dict("records")

        # Repository handles idempotency via ON CONFLICT DO UPDATE
        return await self.repo.upsert_ohlcv(ticker.id, rows)

    async def get_ohlcv(
        self,
        symbol: str,
        start: datetime.date,
        end: datetime.date,
    ) -> list[OHLCV]:
        """Get stored OHLCV records."""
        symbol = symbol.upper()
        ticker = await self.repo.get_ticker_by_symbol(symbol)
        if not ticker:
            raise NotFoundError(f"Ticker {symbol} not found.")

        return await self.repo.get_ohlcv(ticker.id, start, end)

    async def list_tickers(self) -> list[Ticker]:
        """List all initialized tickers."""
        return await self.repo.list_tickers()
