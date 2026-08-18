# QuantPilot AI — Testing Architecture

## 1. Overview

| Framework | Tool |
|---|---|
| Test runner | Pytest |
| Linter | Ruff |
| Coverage | pytest-cov (optional) |
| Async testing | pytest-asyncio |
| HTTP testing | httpx (AsyncClient with FastAPI TestClient) |
| Database testing | Test database with Alembic migrations |

---

## 2. Test Layers

```text
┌─────────────────────────────┐
│      Evaluation Tests       │  ← RAG evaluation harness (15–20 questions)
├─────────────────────────────┤
│     Integration Tests       │  ← API endpoints, database, Celery tasks
├─────────────────────────────┤
│        Unit Tests           │  ← Indicators, metrics, strategy validation
└─────────────────────────────┘
```

---

## 3. Unit Tests

Unit tests cover **deterministic, stateless logic** with no database or external service dependencies.

### 3.1 Indicator Calculations

| Test | What It Verifies |
|---|---|
| `test_sma_basic` | SMA(3) on [1,2,3,4,5] = [NaN, NaN, 2.0, 3.0, 4.0] |
| `test_sma_single_value` | SMA(1) returns the input values |
| `test_sma_insufficient_data` | SMA(10) on 5 data points raises/returns NaN appropriately |
| `test_ema_basic` | EMA(3) on known series matches hand-computed values |
| `test_ema_vs_sma_first_value` | EMA's first valid value equals SMA for the window |
| `test_rsi_basic` | RSI(14) on known series matches hand-computed value |
| `test_rsi_all_gains` | RSI = 100 when all periods are gains |
| `test_rsi_all_losses` | RSI = 0 when all periods are losses |
| `test_macd_basic` | MACD line, signal, histogram match known values |
| `test_bollinger_basic` | Upper/lower bands = SMA ± (std_dev × multiplier) |
| `test_atr_basic` | ATR(14) on known OHLC matches hand-computed value |

### 3.2 Performance Metrics

| Test | What It Verifies |
|---|---|
| `test_total_return` | (final / initial) - 1 |
| `test_cagr` | Compound annual growth rate formula |
| `test_volatility` | Annualized std dev of daily returns |
| `test_sharpe_ratio` | (mean excess return / std) × √252 |
| `test_sharpe_zero_risk_free` | Sharpe with rf=0 |
| `test_sortino_ratio` | Uses only downside deviation |
| `test_max_drawdown` | Peak-to-trough calculation |
| `test_win_rate_all_wins` | 100% win rate |
| `test_win_rate_no_trades` | Returns 0.0 |

### 3.3 Strategy Validation

| Test | What It Verifies |
|---|---|
| `test_valid_strategy` | Well-formed JSON passes validation |
| `test_invalid_indicator` | Unknown indicator name rejected |
| `test_invalid_operator` | Unknown operator rejected |
| `test_missing_entry` | Strategy without entry conditions rejected |
| `test_missing_exit` | Strategy without exit conditions rejected |
| `test_invalid_position_size` | Size > 1.0 or ≤ 0 rejected |
| `test_strategy_version` | Version must be 1 |

### 3.4 Strategy Interpretation

| Test | What It Verifies |
|---|---|
| `test_sma_crossover_strategy` | SMA crossover JSON produces correct backtesting.py Strategy |
| `test_rsi_threshold_strategy` | RSI threshold JSON produces correct entry/exit logic |

---

## 4. Known-Answer Tests

These tests use **hand-computed expected values** to verify quantitative correctness. This is critical for interview credibility.

### 4.1 SMA Known-Answer

```python
def test_sma_known_answer():
    """Hand-computed: SMA(3) of [10, 20, 30, 40, 50]"""
    prices = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    result = SMACalculator.calculate(prices, period=3)

    # Hand computation:
    # SMA[0] = NaN (not enough data)
    # SMA[1] = NaN (not enough data)
    # SMA[2] = (10 + 20 + 30) / 3 = 20.0
    # SMA[3] = (20 + 30 + 40) / 3 = 30.0
    # SMA[4] = (30 + 40 + 50) / 3 = 40.0

    assert_series_equal(result[2:], pd.Series([20.0, 30.0, 40.0], index=[2, 3, 4]))
```

### 4.2 Sharpe Known-Answer

```python
def test_sharpe_known_answer():
    """Hand-computed Sharpe ratio for a simple equity curve."""
    # Equity: 100, 102, 101, 105, 107
    # Daily returns: 0.02, -0.0098, 0.0396, 0.019
    # Mean daily return: 0.01725
    # Std daily return: 0.02046
    # Sharpe (rf=0): (0.01725 / 0.02046) × √252 ≈ 13.39

    equity = pd.Series([100.0, 102.0, 101.0, 105.0, 107.0])
    sharpe = MetricsCalculator(risk_free_rate=0.0).calculate_sharpe(equity)

    assert abs(sharpe - 13.39) < 0.1  # Tolerance for floating point
```

### 4.3 Max Drawdown Known-Answer

```python
def test_max_drawdown_known_answer():
    """Hand-computed: equity peaks at 110, drops to 90, recovers to 105."""
    # Equity: 100, 110, 95, 90, 100, 105
    # Running max: 100, 110, 110, 110, 110, 110
    # Drawdown: 0%, 0%, -13.6%, -18.2%, -9.1%, -4.5%
    # Max drawdown: 18.2%

    equity = pd.Series([100.0, 110.0, 95.0, 90.0, 100.0, 105.0])
    mdd = MetricsCalculator().calculate_max_drawdown(equity)

    assert abs(mdd - 0.1818) < 0.001
```

### 4.4 Total Return Known-Answer

```python
def test_total_return_known_answer():
    """$10,000 → $12,500 = 25% return"""
    total_return = MetricsCalculator().calculate_total_return(initial_capital=10000.0, final_equity=12500.0)
    assert total_return == 0.25
```

---

## 5. Integration Tests

Integration tests verify the interaction between components with a real database.

### 5.1 Test Database Setup

```python
@pytest.fixture(scope="session")
async def test_db():
    """Create a test database and run migrations."""
    # Create test database
    # Run Alembic migrations
    # Yield session factory
    # Drop test database on teardown


@pytest.fixture
async def db_session(test_db):
    """Per-test session with rollback."""
    async with test_db() as session:
        yield session
        await session.rollback()
```

### 5.2 Auth Integration Tests

| Test | What It Verifies |
|---|---|
| `test_register_success` | POST /auth/register → 201, user in DB |
| `test_register_duplicate_email` | POST /auth/register → 409 Conflict |
| `test_login_success` | POST /auth/login → 200, returns JWT |
| `test_login_invalid_password` | POST /auth/login → 401 |
| `test_protected_endpoint_no_token` | GET /strategies → 401 |
| `test_protected_endpoint_valid_token` | GET /strategies → 200 |
| `test_protected_endpoint_expired_token` | GET /strategies → 401 |

### 5.3 Market Data Integration Tests

| Test | What It Verifies |
|---|---|
| `test_get_ohlcv` | GET /market-data/AAPL returns OHLCV data |
| `test_get_ohlcv_invalid_symbol` | GET /market-data/INVALID → 400 |
| `test_ohlcv_date_range` | Query params filter correctly |

### 5.4 Strategy Integration Tests

| Test | What It Verifies |
|---|---|
| `test_create_strategy` | POST /strategies → 201 |
| `test_create_strategy_invalid_json` | POST /strategies with bad rules → 422 |
| `test_get_strategy_own` | GET /strategies/{id} → 200 (own strategy) |
| `test_get_strategy_other_user` | GET /strategies/{id} → 403 (other user's) |
| `test_list_strategies` | GET /strategies returns only user's strategies |

### 5.5 Backtest Integration Tests

| Test | What It Verifies |
|---|---|
| `test_submit_backtest` | POST /backtests → 202, status=QUEUED |
| `test_get_backtest_status` | GET /backtests/{id} returns current status |
| `test_get_backtest_results_completed` | GET /backtests/{id}/results → 200 when COMPLETED |
| `test_get_backtest_results_pending` | GET /backtests/{id}/results → 404 when not COMPLETED |

### 5.6 Document Integration Tests

| Test | What It Verifies |
|---|---|
| `test_upload_pdf` | POST /documents → 201 with valid PDF |
| `test_upload_non_pdf` | POST /documents with .txt → 400 |
| `test_upload_too_large` | POST /documents with oversized file → 400 |
| `test_list_documents` | GET /documents returns user's documents |

### 5.7 Repository Integration Tests

| Test | What It Verifies |
|---|---|
| `test_user_repo_create_and_get` | Create user, retrieve by email |
| `test_ohlcv_repo_upsert` | Upsert handles duplicates correctly |
| `test_document_chunk_vector_search` | pgvector cosine search returns ranked results |

---

## 6. AI Tests

AI tests are split into **deterministic** and **stochastic** layers.

### 6.1 Deterministic: Tool Invocation Tests

Test that tools correctly delegate to services and format output:

| Test | What It Verifies |
|---|---|
| `test_get_market_data_tool` | Tool calls MarketDataService and returns formatted OHLCVBars |
| `test_calculate_indicators_tool` | Tool calls IndicatorService and returns formatted result |
| `test_run_backtest_tool` | Tool calls BacktestService.submit and returns handle |
| `test_get_performance_metrics_tool` | Tool calls BacktestService.get_results and returns metrics |
| `test_search_documents_tool` | Tool calls RetrievalService.search and returns ChunkWithCitation[] |
| `test_tool_error_handling` | Tool catches service exceptions and returns error message |

### 6.2 Stochastic: Agent Integration Tests (Optional)

These tests verify end-to-end agent behavior with a real LLM. They are **not** part of CI (they require API keys and are non-deterministic).

| Test | What It Verifies |
|---|---|
| `test_agent_calls_get_market_data` | Agent calls the right tool for "What's AAPL's price?" |
| `test_agent_handles_tool_error` | Agent provides graceful response when tool fails |
| `test_agent_cites_documents` | Agent includes citations when using search_documents |

---

## 7. Evaluation Tests

The evaluation harness runs 15–20 pre-defined question/answer pairs:

```python
def test_evaluation_harness():
    """Run all evaluation questions and assert minimum quality thresholds."""
    results = evaluation_service.run_full_evaluation()

    # Aggregate metrics
    retrieval_hit_rate = sum(r.retrieval_hit_at_k for r in results) / len(results)
    citation_accuracy = sum(r.citation_correct for r in results) / len(results)
    avg_answer_score = sum(r.answer_score for r in results) / len(results)

    # Minimum thresholds (adjust based on actual performance)
    assert retrieval_hit_rate >= 0.7, f"Retrieval hit rate too low: {retrieval_hit_rate}"
    assert citation_accuracy >= 0.6, f"Citation accuracy too low: {citation_accuracy}"
```

---

## 8. Test Directory Structure

```text
tests/
├── conftest.py              # Shared fixtures (db, client, auth)
├── unit/
│   ├── test_indicators.py   # SMA, EMA, RSI, MACD, Bollinger, ATR
│   ├── test_metrics.py      # Sharpe, Sortino, CAGR, drawdown, etc.
│   ├── test_strategy_validation.py
│   └── test_strategy_interpreter.py
├── integration/
│   ├── test_auth.py
│   ├── test_market_data.py
│   ├── test_strategies.py
│   ├── test_backtests.py
│   ├── test_documents.py
│   ├── test_repositories.py
│   └── test_retrieval.py
├── ai/
│   ├── test_tools.py        # Deterministic tool tests
│   └── test_agent.py        # Optional: stochastic agent tests (not in CI)
└── evaluation/
    └── test_eval_harness.py  # RAG evaluation with known Q/A pairs
```

---

## 9. CI Integration

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install ruff
      - run: ruff check .
      - run: ruff format --check .

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: quantpilot_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        ports: ["5432:5432"]
      redis:
        image: redis:7
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt -r requirements-test.txt
      - run: pytest tests/unit/ tests/integration/ -v --tb=short
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/quantpilot_test
          REDIS_URL: redis://localhost:6379/0
          JWT_SECRET_KEY: test-secret-key
```

**Note:** AI agent tests and evaluation tests are **not** in CI — they require a Gemini API key and produce non-deterministic results.

---

## 10. Testing Principles

1. **Unit tests are fast** — no database, no network, pure computation
2. **Integration tests use real database** — Alembic migrations, real PostgreSQL + pgvector
3. **Known-answer tests are mandatory** — hand-computed expected values for every quant calculation
4. **AI tool tests are deterministic** — mock the LLM, test tool dispatch and error handling
5. **Evaluation tests measure, not assert** — the harness produces metrics for human review
6. **CI runs lint + unit + integration** — no stochastic tests in CI
