# QuantPilot AI — Phase 2 Report

## Objective
Build the deterministic market-data foundation required by later backtesting and AI tools.

## Implementation Details

### Database & Models
- `tickers` model added (fields: `id`, `symbol`, `name`, `sector`). `is_active` explicitly excluded per design correction.
- `ohlcv` model added.
- Added `UniqueConstraint("ticker_id", "date")` to ensure idempotent upserts.
- Single Alembic migration created and successfully run to deploy both tables.

### Infrastructure Layer
- Created `YFinanceAdapter`.
- Uses `asyncio.get_event_loop().run_in_executor()` to wrap blocking `yf.download` network calls to avoid starving FastAPI event loop.
- Normalizes data (handles MultiIndex drops, renames to `[date, open, high, low, close, volume]`).
- Hardcoded fixed universe of ~35 standard US equity tickers.

### Repository & Services
- **Repository**: Uses PostgreSQL `INSERT ... ON CONFLICT DO UPDATE SET ...` for high-performance and resilient upserts.
- **Market Data Service**: Validates symbols against fixed universe, pulls from Adapter, and delegates to repository for DB persistence.
- **Indicator Service**: Evaluates indicator lookback requirements, pads the start date query to include necessary historical warm-up rows, evaluates pure-functions, trims the warm-up, and checks for insufficient data constraints.

### Pure Domain Indicators
Implemented 6 calculators matching explicit mathematical conventions:
- **SMA**: Basic rolling mean
- **EMA**: Exponential with `adjust=False`
- **RSI**: Wilder's smoothing method
- **MACD**: `fast=12`, `slow=26`, `signal=9` EMAs
- **Bollinger Bands**: Simple mean and standard deviation (`ddof=1`)
- **ATR**: True range computation with Wilder's smoothing

### API Layer
Added endpoints secured via the `get_current_user` dependency from Phase 1:
- `GET /api/v1/market-data/tickers`
- `GET /api/v1/market-data/{symbol}`
- `POST /api/v1/market-data/{symbol}/ingest`
- `GET /api/v1/indicators/{symbol}`

### Testing
- Fully mocked yfinance adapter in all `pytest` runs using `monkeypatch`.
- Comprehensive known-answer test suite built on a hand-rolled synthetic price series to verify mathematical outputs exactly.
- Asserts built for idempotency verification (running ingest multiple times produces no duplicate rows).

## Verification Results

The Phase 2 implementation was validated against a strict verification checklist:
- **Clean Environment (Local)**: Due to lack of Docker in the test environment, the test was performed manually against a local `quantpilot` asyncpg database.
- **Database Migrations**: Ran cleanly via Alembic. Verified the existence of `users`, `tickers`, and `ohlcv`.
- **Data Ingestion**: Ran `python -m scripts.ingest_market_data`. Successfully seeded the 35 fixed universe tickers and fetched 8,785 OHLCV rows for the trailing 1-year window without silent errors.
- **Idempotency**: Executed the ingestion script twice. The number of rows remained exactly 8,785. A manual PostgreSQL validation query proved that exactly zero `(ticker_id, date)` duplicates exist.
- **Authenticated API**: Extensively tested via `httpx.AsyncClient` bridging the Phase 1 login authentication. 
  - `GET /api/v1/market-data/tickers` works correctly.
  - `GET /api/v1/market-data/AAPL` properly trims to exact requested date ranges.
  - `GET /api/v1/indicators/AAPL?indicator=rsi` dynamically calculates lookback ranges, performs Wilders RSI calculations, and trims results starting from the exact requested date perfectly.
  - Checked insufficient historical data (e.g., querying 200-SMA on just 1 month of history) and safely rejected it with a graceful HTTP 400 validation error detailing the required trading days needed.
- **Numerical Verification**: Unit tests cover SMA, EMA, RSI, MACD, Bollinger Bands, and ATR. Tested against synthetic 30-day linear sequences to assert exact mathematical values outputting `NaNs` perfectly aligned with period windows.
- **Async Safety**: `yf.download()` was reviewed and relies solely on `run_in_executor()` ensuring the FastAPI loop never blocks.
- **Scope Audit**: Passed. No strategy execution or Celery dependencies were introduced.

## Status
**Phase 2 Status: APPROVED**
