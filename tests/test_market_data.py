import datetime

import pandas as pd
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DataProviderError
from app.services.indicator_service import IndicatorService
from app.services.market_data_service import MarketDataService


# Mock yfinance to avoid network calls during tests
class MockYFinanceAdapter:
    def __init__(self, should_fail=False, empty=False):
        self.should_fail = should_fail
        self.empty = empty

    async def fetch(self, symbol, start, end):
        if self.should_fail:
            raise DataProviderError("Mock provider failure")
        if self.empty:
            return pd.DataFrame()

        # Create enough synthetic data
        dates = pd.date_range(start, periods=1000)
        df = pd.DataFrame(
            {
                "date": [d.date() for d in dates],
                "open": [100.0] * 1000,
                "high": [105.0] * 1000,
                "low": [95.0] * 1000,
                "close": [102.0] * 1000,
                "volume": [1000] * 1000,
            }
        )
        # Filter to requested range
        df = df[(df["date"] >= start) & (df["date"] < end)]
        return df


@pytest.fixture
def override_adapter(monkeypatch):
    def _override(should_fail=False, empty=False):
        monkeypatch.setattr(
            "app.services.market_data_service.YFinanceAdapter",
            lambda: MockYFinanceAdapter(should_fail=should_fail, empty=empty),
        )

    return _override


@pytest.mark.asyncio
async def test_market_data_ingestion_and_retrieval(db_session: AsyncSession, override_adapter):
    override_adapter()
    service = MarketDataService(db_session)

    start_date = datetime.date(2024, 1, 1)
    end_date = datetime.date(2024, 2, 1)  # 31 days

    # 1. Ingest
    rows = await service.ingest_ticker("AAPL", start_date, end_date)
    assert rows == 31

    # 2. Retrieve
    data = await service.get_ohlcv("AAPL", start_date, end_date)
    assert len(data) == 31
    assert data[0].date == start_date
    assert float(data[0].open) == 100.0


@pytest.mark.asyncio
async def test_market_data_idempotency(db_session: AsyncSession, override_adapter):
    override_adapter()
    service = MarketDataService(db_session)

    start_date = datetime.date(2024, 1, 1)
    end_date = datetime.date(2024, 1, 10)  # 9 days

    # First ingest
    rows1 = await service.ingest_ticker("AAPL", start_date, end_date)
    assert rows1 == 9

    # Second ingest
    rows2 = await service.ingest_ticker("AAPL", start_date, end_date)
    assert rows2 == 9  # Upserted 9 rows

    # Verify no duplicates
    data = await service.get_ohlcv("AAPL", start_date, end_date)
    assert len(data) == 9


@pytest.mark.asyncio
async def test_indicator_warmup(db_session: AsyncSession, override_adapter):
    # Setup data
    override_adapter()
    md_service = MarketDataService(db_session)
    # Ingest lots of data for warm-up
    await md_service.ingest_ticker("AAPL", datetime.date(2023, 1, 1), datetime.date(2024, 3, 1))

    # Test Indicator Service
    ind_service = IndicatorService(db_session)

    req_start = datetime.date(2024, 1, 1)
    req_end = datetime.date(2024, 1, 31)

    dates, values = await ind_service.calculate("AAPL", "sma", {"period": 20}, req_start, req_end)

    # Verify results start EXACTLY at req_start (no warm-up rows returned)
    assert len(dates) > 0
    assert dates[0] >= req_start
    assert dates[-1] <= req_end

    # Value should not be NaN (meaning warm-up worked,
    # because if it didn't, the first 19 days would be NaN)
    assert not pd.isna(values[0])


@pytest.mark.asyncio
async def test_indicator_insufficient_data(db_session: AsyncSession, override_adapter):
    # Setup data
    override_adapter()
    md_service = MarketDataService(db_session)
    # Only ingest data from 2024-01-01
    await md_service.ingest_ticker("AAPL", datetime.date(2024, 1, 1), datetime.date(2024, 3, 1))

    ind_service = IndicatorService(db_session)

    # Request starting 2024-01-05 with a 20-day SMA
    # This requires data from ~mid-December, which doesn't exist.
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError, match="Insufficient historical data"):
        await ind_service.calculate(
            "AAPL",
            "sma",
            {"period": 20},
            datetime.date(2024, 1, 5),
            datetime.date(2024, 1, 31),
        )
