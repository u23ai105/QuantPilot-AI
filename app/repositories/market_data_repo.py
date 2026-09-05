"""Market data repository — OHLCV and ticker persistence."""

import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ohlcv import OHLCV
from app.models.ticker import Ticker


class MarketDataRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_ticker_by_symbol(self, symbol: str) -> Ticker | None:
        stmt = select(Ticker).where(Ticker.symbol == symbol)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_ticker(self, symbol: str, name: str, sector: str | None = None) -> Ticker:
        ticker = Ticker(symbol=symbol, name=name, sector=sector)
        self.session.add(ticker)
        await self.session.flush()
        return ticker

    async def list_tickers(self) -> list[Ticker]:
        stmt = select(Ticker).order_by(Ticker.symbol)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_ohlcv(self, ticker_id: int, rows: list[dict]) -> int:
        """Bulk upsert OHLCV rows using ON CONFLICT DO UPDATE.

        Args:
            ticker_id: FK to tickers table.
            rows: List of dicts with keys:
                  date, open, high, low, close, volume.

        Returns:
            Number of rows upserted.
        """
        if not rows:
            return 0

        values = [
            {
                "ticker_id": ticker_id,
                "date": row["date"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
            }
            for row in rows
        ]

        stmt = insert(OHLCV).values(values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ohlcv_ticker_date",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()
        return len(values)

    async def get_ohlcv(
        self,
        ticker_id: int,
        start: datetime.date,
        end: datetime.date,
    ) -> list[OHLCV]:
        """Get OHLCV records for a ticker in a date range.

        Args:
            ticker_id: FK to tickers table.
            start: Start date (inclusive).
            end: End date (inclusive).

        Returns:
            List of OHLCV records ordered by date.
        """
        stmt = (
            select(OHLCV)
            .where(
                OHLCV.ticker_id == ticker_id,
                OHLCV.date >= start,
                OHLCV.date <= end,
            )
            .order_by(OHLCV.date)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_ohlcv_date_range(self, ticker_id: int) -> tuple[datetime.date, datetime.date] | None:
        """Return (min_date, max_date) of stored OHLCV for a ticker, or None if there is none.

        Used to validate a requested backtest window against available price data so an
        out-of-range request fails fast with a clear 400, instead of an opaque async
        backtest FAILED at the worker's data-load step.
        """
        stmt = select(func.min(OHLCV.date), func.max(OHLCV.date)).where(OHLCV.ticker_id == ticker_id)
        result = await self.session.execute(stmt)
        min_date, max_date = result.one()
        if min_date is None or max_date is None:
            return None
        return min_date, max_date
