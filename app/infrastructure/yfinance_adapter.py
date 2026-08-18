"""yfinance market data adapter.

Isolates the synchronous yfinance library behind an async-safe interface.
Blocking yfinance.download() is executed in a thread executor to avoid
blocking the FastAPI event loop.
"""

import asyncio
import datetime
import logging

import pandas as pd
import yfinance as yf

from app.core.exceptions import DataProviderError

logger = logging.getLogger(__name__)

# Fixed ticker universe (~35 tickers across sectors)
TICKER_UNIVERSE: list[dict[str, str]] = [
    # Technology
    {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology"},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "sector": "Technology"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "Technology"},
    {"symbol": "AMZN", "name": "Amazon.com Inc.", "sector": "Technology"},
    {"symbol": "META", "name": "Meta Platforms Inc.", "sector": "Technology"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "sector": "Technology"},
    {"symbol": "TSM", "name": "Taiwan Semiconductor", "sector": "Technology"},
    # Financials
    {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "sector": "Financials"},
    {"symbol": "BAC", "name": "Bank of America Corp.", "sector": "Financials"},
    {"symbol": "GS", "name": "Goldman Sachs Group", "sector": "Financials"},
    {"symbol": "V", "name": "Visa Inc.", "sector": "Financials"},
    {"symbol": "MA", "name": "Mastercard Inc.", "sector": "Financials"},
    # Healthcare
    {"symbol": "JNJ", "name": "Johnson & Johnson", "sector": "Healthcare"},
    {"symbol": "UNH", "name": "UnitedHealth Group", "sector": "Healthcare"},
    {"symbol": "PFE", "name": "Pfizer Inc.", "sector": "Healthcare"},
    {"symbol": "ABBV", "name": "AbbVie Inc.", "sector": "Healthcare"},
    {"symbol": "MRK", "name": "Merck & Co.", "sector": "Healthcare"},
    # Consumer
    {"symbol": "KO", "name": "Coca-Cola Company", "sector": "Consumer Staples"},
    {"symbol": "PEP", "name": "PepsiCo Inc.", "sector": "Consumer Staples"},
    {"symbol": "PG", "name": "Procter & Gamble", "sector": "Consumer Staples"},
    {"symbol": "WMT", "name": "Walmart Inc.", "sector": "Consumer Staples"},
    {"symbol": "COST", "name": "Costco Wholesale", "sector": "Consumer Staples"},
    # Energy
    {"symbol": "XOM", "name": "Exxon Mobil Corporation", "sector": "Energy"},
    {"symbol": "CVX", "name": "Chevron Corporation", "sector": "Energy"},
    {"symbol": "COP", "name": "ConocoPhillips", "sector": "Energy"},
    # Industrials
    {"symbol": "CAT", "name": "Caterpillar Inc.", "sector": "Industrials"},
    {"symbol": "BA", "name": "Boeing Company", "sector": "Industrials"},
    {"symbol": "HON", "name": "Honeywell International", "sector": "Industrials"},
    {"symbol": "UPS", "name": "United Parcel Service", "sector": "Industrials"},
    # Communication
    {"symbol": "DIS", "name": "Walt Disney Company", "sector": "Communication"},
    {"symbol": "NFLX", "name": "Netflix Inc.", "sector": "Communication"},
    {"symbol": "CMCSA", "name": "Comcast Corporation", "sector": "Communication"},
    # Real Estate / Utilities
    {"symbol": "NEE", "name": "NextEra Energy", "sector": "Utilities"},
    {"symbol": "SO", "name": "Southern Company", "sector": "Utilities"},
    # Materials
    {"symbol": "LIN", "name": "Linde plc", "sector": "Materials"},
]

VALID_SYMBOLS: set[str] = {t["symbol"] for t in TICKER_UNIVERSE}


class YFinanceAdapter:
    """Wraps yfinance library. Normalizes output.

    All blocking I/O is delegated to a thread executor so the
    FastAPI async event loop is never blocked.
    """

    def _fetch_sync(
        self,
        symbol: str,
        start: datetime.date,
        end: datetime.date,
    ) -> pd.DataFrame:
        """Synchronous yfinance fetch. Must NOT be called on event loop."""
        try:
            df = yf.download(
                symbol,
                start=start.isoformat(),
                end=end.isoformat(),
                progress=False,
                auto_adjust=True,
            )
        except Exception as exc:
            raise DataProviderError(f"yfinance error for {symbol}: {exc}") from exc

        if df is None or df.empty:
            raise DataProviderError(f"No data returned by yfinance for {symbol} ({start} to {end})")

        return self._normalize(df, symbol)

    def _normalize(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Normalize yfinance output into standard columns."""
        # Handle MultiIndex columns (yfinance >= 0.2.18)
        if isinstance(df.columns, pd.MultiIndex):
            df = df.droplevel("Ticker", axis=1)

        # Standardize column names to lowercase
        df.columns = [c.lower() for c in df.columns]

        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise DataProviderError(f"Missing columns for {symbol}: {missing}")

        # Reset index — date becomes a column
        df = df.reset_index()

        # Normalize date column name
        date_col = None
        for col in df.columns:
            if col.lower() in ("date", "datetime"):
                date_col = col
                break
        if date_col is None:
            raise DataProviderError(f"No date column found for {symbol}")
        df = df.rename(columns={date_col: "date"})
        df["date"] = pd.to_datetime(df["date"]).dt.date

        # Select and order columns
        df = df[["date", "open", "high", "low", "close", "volume"]]

        # Drop rows with any NaN in OHLCV columns
        df = df.dropna(subset=["open", "high", "low", "close", "volume"])

        # Validate: high >= low
        df = df[df["high"] >= df["low"]]

        # Validate: volume >= 0
        df = df[df["volume"] >= 0]

        if df.empty:
            raise DataProviderError(f"All data rows invalid for {symbol} after validation")

        return df

    async def fetch(
        self,
        symbol: str,
        start: datetime.date,
        end: datetime.date,
    ) -> pd.DataFrame:
        """Async-safe fetch. Runs blocking yfinance in thread executor.

        Args:
            symbol: Ticker symbol (must be in VALID_SYMBOLS).
            start: Start date (inclusive).
            end: End date (exclusive for yfinance).

        Returns:
            Normalized, validated OHLCV DataFrame.

        Raises:
            DataProviderError: On network failure or invalid data.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync, symbol, start, end)
