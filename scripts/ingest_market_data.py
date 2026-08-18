"""Ingest market data for fixed ticker universe.

Usage: python -m scripts.ingest_market_data
"""

import asyncio
import datetime
import logging

from app.core.db import async_session_maker
from app.core.logging import setup_logging
from app.infrastructure.yfinance_adapter import TICKER_UNIVERSE
from app.services.market_data_service import MarketDataService

setup_logging()
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting market data ingestion")

    # Fetch 1 year of historical data
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=365)

    success_count = 0
    failure_count = 0

    async with async_session_maker() as session:
        service = MarketDataService(session)

        for ticker_def in TICKER_UNIVERSE:
            symbol = ticker_def["symbol"]
            logger.info(f"Ingesting {symbol}...")
            try:
                # We reuse the service which fetches and upserts
                rows = await service.ingest_ticker(symbol, start_date, end_date)
                logger.info(f"Successfully ingested {rows} rows for {symbol}")
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to ingest {symbol}: {e}")
                failure_count += 1

    logger.info(f"Ingestion complete. Success: {success_count}, Failure: {failure_count}, Total: {len(TICKER_UNIVERSE)}")


if __name__ == "__main__":
    asyncio.run(main())
