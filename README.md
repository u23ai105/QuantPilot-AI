# QuantPilot AI

**Agentic Financial Research, Quantitative Backtesting, and Document RAG Platform**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic%20Workflows-1C3C3C)](https://langchain-ai.github.io/langgraph/)
[![PostgreSQL + pgvector](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Celery + Redis](https://img.shields.io/badge/Celery-Redis-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![React + TypeScript](https://img.shields.io/badge/Frontend-React%20%2B%20Vite%20%2B%20TS-61DAFB?logo=react&logoColor=black)](https://vite.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

QuantPilot AI is a full-stack quantitative research assistant that combines a **LangGraph tool-calling AI agent**, a **deterministic technical indicator & strategy backtesting engine**, and a **multi-tenant PDF RAG pipeline** backed by PostgreSQL (`pgvector`), Redis, and Celery.

Rather than letting an LLM hallucinate prices, ratios, or filing metrics, QuantPilot enforces strict tool-grounded execution: market data, indicators, backtests, and SEC/annual-report citations are always computed or retrieved through typed, deterministic backend services.

---

## Architecture

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                     React + TypeScript + Vite SPA                          │
│  Research Workspace (SSE) │ Market Data │ Strategies │ Backtests │ Docs    │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     │ HTTPS / REST + Server-Sent Events
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Application                               │
│  MetricsMiddleware ─▶ RequestIdMiddleware ─▶ CORS ─▶ RateLimitMiddleware   │
├────────────────────────────────────────────────────────────────────────────┤
│  /api/v1/auth          /api/v1/market-data       /api/v1/indicators        │
│  /api/v1/strategies    /api/v1/backtests         /api/v1/documents         │
│  /api/v1/conversations /api/v1/models            /health  /ready  /metrics │
├────────────────────────────────────┬───────────────────────────────────────┤
│        LangGraph Agent             │          Domain & Services            │
│  START ─▶ agent_node ◀─▶ tool_node │  • Pure-Pandas Indicators (6)         │
│  • Gemini / NVIDIA NIM (429 retry) │  • Declarative Strategy Interpreter   │
│  • 5 Pydantic-typed tools          │  • YFinance Async Thread Adapter      │
│  • Stateless graph + DB memory     │  • PDF Extractor, Chunker & RAG Eval  │
└──────────────┬─────────────────────┴──────────────────┬────────────────────┘
               │                                        │
               ▼                                        ▼
┌──────────────────────────────┐         ┌───────────────────────────────────┐
│   PostgreSQL + pgvector      │         │       Redis & Celery Workers      │
│  • Users, Tickers, OHLCV     │         │  • Broker & Result Backend        │
│  • Strategies & Backtests    │         │  • Queue: `backtest`              │
│  • Conversations & Messages  │         │  • Queue: `embedding`             │
│  • DocumentChunks Vector(768)│         │  • Fixed-Window Rate Limiter      │
│  • EvalQuestions & EvalRuns  │         │  • 24h RAG Query-Embedding Cache  │
└──────────────────────────────┘         └───────────────────────────────────┘
```

---

## Key Features

### 1. Agentic Research Workspace (LangGraph + SSE Streaming)
* **Tool-Grounded Reasoning:** Compiled LangGraph loop (`agent_node ↔ safe_tool_node`) with a safe tool-error wrapper so exceptions return structured `ToolMessage` errors that the agent can recover from gracefully.
* **Real-Time SSE Streaming:** `POST /api/v1/conversations/{id}/messages` streams `tool_start`, `tool_end`, `token`, `error`, and `done` events over `text/event-stream`, giving live visibility into tool execution alongside streamed markdown replies.
* **Multi-Provider LLM Switching:** Supports **Google Gemini** (`gemini-3.6-flash`) and **NVIDIA NIM** (`nvidia/nemotron-3-ultra-550b-a55b` via OpenAI-compatible client with exponential backoff on HTTP `429`), switchable per message from the UI or API.
* **Five Typed Agent Tools:**
  * `get_market_data` — Fetch stored OHLCV price history.
  * `calculate_indicators` — Compute technical indicators with automatic warm-up lookback.
  * `run_backtest` — Queue asynchronous strategy backtests on behalf of the authenticated user.
  * `get_performance_metrics` — Read authoritative stored backtest statuses and metrics.
  * `search_documents` — Semantic search across user-owned PDF filings with mandatory `` citations.
* **Postgres-Backed Memory:** Conversations are persisted in PostgreSQL (`conversations` and `messages`) rather than an in-process LangGraph checkpointer, keeping the API stateless across workers.

### 2. Market Data & Pure-Domain Technical Indicators
* **Fixed 35-Ticker Universe:** Cross-sector equities spanning Technology, Financials, Healthcare, Consumer Staples, Energy, Industrials, Communication, Utilities, and Materials.
* **Async-Safe `yfinance` Ingestion:** Runs blocking `yfinance.download()` calls in a thread executor, validates OHLCV invariants (`high >= low`, `volume >= 0`, NaN removal), and performs idempotent PostgreSQL `ON CONFLICT DO UPDATE` upserts.
* **Six Deterministic Indicators:** Implemented as pure Pandas calculators in `app/domain/indicators/`:
  * `sma` (Simple Moving Average)
  * `ema` (Exponential Moving Average)
  * `rsi` (Wilder's Relative Strength Index)
  * `macd` (MACD line, signal line, histogram)
  * `bollinger` (Middle, upper, and lower bands)
  * `atr` (Wilder's Average True Range)
* **Automatic Warm-Up Handling:** Indicator requests transparently fetch required pre-window trading bars before `start` so every returned data point is fully converged.

### 3. Declarative Strategy Engine & Asynchronous Backtesting
* **No Arbitrary Code Execution:** Strategies are authored as validated version-1 JSON rules (`entry` / `exit` groups with `AND`/`OR` logic, comparison & crossover operators, and `fixed_fraction` position sizing) and validated eagerly on creation.
* **Dynamic `backtesting.py` Compilation:** `StrategyInterpreter` compiles JSON rules into a `backtesting.py` `Strategy` subclass with 100-day indicator warm-up gating and next-bar open execution (`trade_on_close=False`).
* **Idempotent Async Execution:** Backtests queue onto Celery (`backtest` queue) with atomic `QUEUED → RUNNING → COMPLETED | FAILED` claiming. Supplying an `Idempotency-Key` header prevents duplicate runs on retries and returns `409 Conflict` if the key is reused with different parameters.
* **Comprehensive Performance Metrics:** Computes Total Return, CAGR, Annualized Volatility, Sharpe Ratio, Sortino Ratio, Max Drawdown, Win Rate, Total Trades, Equity Curve, and full Trade Log—visualized with lazy-loaded interactive Recharts area charts.

### 4. Financial Document RAG Pipeline
* **Validated PDF Ingestion:** Enforces `application/pdf` MIME type, `%PDF-` magic-byte verification, 50 MB size ceiling, and UUID-renamed disk storage to prevent path traversal.
* **Page-Boundary Chunking & Async Indexing:** Celery (`embedding` queue) extracts text via PyMuPDF (`fitz`), chunks strictly within page boundaries (`max_chars=2000`, `min_chars=50`), generates 768-dimensional vectors, and bulk-inserts them into PostgreSQL `pgvector`.
* **Dual 768-Dim Embedding Backends:**
  * **Local FastEmbed (`BAAI/bge-base-en-v1.5`)** — Default; runs locally on CPU via ONNX runtime (`threads=2`) with zero external API quota or rate limits.
  * **Google Gemini Embeddings (`models/gemini-embedding-001` / `gemini-embedding-2`)** — Cloud embeddings with Matryoshka dimensionality reduction to `768` and quota-aware backoff.
* **Redis Query-Embedding Cache:** SHA-256 keyed (`embed:query:<model>:<dim>:<hash>`, 24-hour TTL, fail-open) to avoid redundant query vectorization.
* **SQL-Enforced Tenant Isolation:** Vector similarity search joins `documents` and filters by `user_id` inside PostgreSQL before ranking by cosine distance.
* **Deterministic RAG Evaluation:** `EvalService` + `eval_questions`/`eval_runs` models score Retrieval Hit@K, Citation Hit, canonical bracket formatting, and numeric/string answer accuracy.

### 5. Production Security, Rate Limiting & Observability
* **Authentication & Isolation:** Bcrypt password hashing + HS256 JWT bearer authentication. Sequential resource IDs (strategies, backtests) return `404` for non-owners to prevent ID enumeration.
* **Redis Fixed-Window Rate Limiting:** Fail-open middleware keyed by authenticated user ID (or client IP for auth routes), exposing `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, and `Retry-After` headers:
  * Chat messages: `20 req/min`
  * Backtest submission, market-data ingestion, PDF upload, auth login/register: `10 req/min`
* **Bounded-Cardinality Prometheus Metrics (`GET /metrics`):** Hand-rolled metrics labeled by matched FastAPI route template (preventing series explosion from path IDs or 404 scanners), tracking HTTP requests, latency histograms, unhandled exceptions, rate-limit rejections, backtest submission/replay counts, and query-embedding cache hit/miss ratios. Supports optional constant-time Bearer token protection via `METRICS_TOKEN`.
* **Structured Logging & Health Probes:** JSON logs via `structlog` with `X-Request-ID` propagation, plus `/health` (liveness) and `/ready` (PostgreSQL + Redis readiness) probes displayed live in the UI header.

---

## Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **API & Backend** | Python 3.11+, FastAPI, Uvicorn, Pydantic v2, `structlog`, `prometheus-client` |
| **AI & RAG** | LangGraph, LangChain (`langchain-google-genai`, `langchain-openai`), FastEmbed (ONNX), PyMuPDF (`fitz`) |
| **Quant & Data** | Pandas, NumPy, `backtesting.py`, `yfinance` |
| **Database & Vector Store** | PostgreSQL, `pgvector`, SQLAlchemy 2.0 (Async + `asyncpg`), Alembic |
| **Async Workers & Cache** | Celery 5, Redis (`redis.asyncio`), Flower (dev) |
| **Frontend** | React, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router, Recharts, Lucide Icons |
| **Testing & Tooling** | Pytest, `pytest-asyncio`, `pytest-cov`, `httpx`, Ruff |

---

## Project Structure

```text
u23ai105-quantpilot-ai/
├── alembic.ini                 # Alembic database migration config
├── Dockerfile                  # Python 3.11-slim backend image
├── pyproject.toml              # Dependencies, Ruff, Pytest & coverage config
├── conftest.py                 # Root test bootstrap (disables rate limit in suite)
├── .env.example                # Environment variable template
├── app/
│   ├── main.py                 # FastAPI app factory, middleware stack, optional embedded Celery worker
│   ├── ai/                     # LangGraph graph, AgentService, LLM factory, model registry, embeddings & cache
│   │   └── tools/              # 5 Pydantic-typed LangChain tools + ContextVar auth/session injection
│   ├── api/
│   │   ├── health.py           # /health, /ready, /metrics
│   │   ├── deps.py             # OAuth2/JWT user dependency
│   │   ├── middleware/         # MetricsMiddleware, RateLimitMiddleware
│   │   └── v1/                 # auth, market_data, indicators, strategies, backtests, conversations, documents, models
│   ├── core/                   # Settings, async DB engine, Redis cache, rate limiter, Prometheus metrics, security, logging
│   ├── domain/                 # Pure business logic (6 indicators, StrategyValidator, StrategyInterpreter, MetricsCalculator)
│   ├── infrastructure/         # Async-safe YFinanceAdapter & 35-ticker universe
│   ├── models/                 # SQLAlchemy ORM models (User, Ticker, OHLCV, Strategy, Backtest, Conversation, Document, Eval)
│   ├── repositories/           # Data-access layer with ownership scoping & pgvector cosine search
│   ├── schemas/                # Pydantic request/response contracts
│   ├── services/               # Application orchestration + RAG PDF extractor, chunker & EvalService
│   └── workers/                # Celery app & tasks (run_backtest, embed_document, ping_task)
└── frontend/
    ├── vite.config.ts
    ├── tailwind.config.js
    └── src/
        ├── app/                # QueryClientProvider & React Router setup
        ├── components/layout/  # AppShell, SidebarNavigation, TopHeader (live /ready status)
        ├── features/           # auth, research, market, strategies, backtests, documents
        └── lib/api/            # Typed fetch client & resource wrappers
```

---

## API Reference

All versioned endpoints are served under `/api/v1` and require `Authorization: Bearer <token>` unless noted otherwise. Interactive OpenAPI docs are available at `/docs`.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Liveness probe (unauthenticated) |
| `GET` | `/ready` | Readiness probe checking PostgreSQL & Redis (unauthenticated) |
| `GET` | `/metrics` | Prometheus metrics exposition (optional `METRICS_TOKEN` Bearer auth) |
| `POST` | `/api/v1/auth/register` | Register a new user account (unauthenticated, 10/min) |
| `POST` | `/api/v1/auth/login` | Exchange email/password for a JWT access token (unauthenticated, 10/min) |
| `GET` | `/api/v1/auth/me` | Return the authenticated user profile |
| `GET` | `/api/v1/models` | List available chat LLMs and embedding models |
| `GET` | `/api/v1/market-data/tickers` | List ingested tickers |
| `GET` | `/api/v1/market-data/{symbol}` | Query stored daily OHLCV bars (`?start=YYYY-MM-DD&end=YYYY-MM-DD`) |
| `POST` | `/api/v1/market-data/{symbol}/ingest` | Fetch from `yfinance` and upsert bars (10/min) |
| `GET` | `/api/v1/indicators/{symbol}` | Compute `sma`, `ema`, `rsi`, `macd`, `bollinger`, or `atr` with warm-up |
| `POST` | `/api/v1/strategies` | Validate and store a declarative JSON strategy |
| `GET` | `/api/v1/strategies` | List strategies owned by the caller |
| `GET` | `/api/v1/strategies/{strategy_id}` | Fetch a single strategy |
| `POST` | `/api/v1/backtests` | Queue an async backtest (`202 Accepted`; supports `Idempotency-Key`, 10/min) |
| `GET` | `/api/v1/backtests` | List caller's backtests (paginated via `limit` & `offset`) |
| `GET` | `/api/v1/backtests/{backtest_id}` | Poll backtest status (`QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`) |
| `GET` | `/api/v1/backtests/{backtest_id}/results` | Retrieve performance metrics, equity curve, and trade log |
| `POST` | `/api/v1/documents` | Upload a PDF (`202 Accepted`; queues extraction & embedding, 10/min) |
| `GET` | `/api/v1/documents` | List uploaded documents and processing status |
| `GET` | `/api/v1/documents/{document_id}` | Get document metadata and status |
| `DELETE` | `/api/v1/documents/{document_id}` | Delete document, stored PDF, and embedded chunks |
| `GET` | `/api/v1/documents/{document_id}/search` | Vector similarity search inside a specific document |
| `POST` | `/api/v1/conversations` | Create a new research conversation |
| `POST` | `/api/v1/conversations/{id}/messages` | Send a prompt and stream SSE response (`text/event-stream`, 20/min) |
| `GET` | `/api/v1/conversations/{id}/messages` | Retrieve persisted conversation history |

---

## Declarative Strategy Schema Example

Strategies are defined in JSON (`version: 1`) and validated against the indicator registry (`sma`, `ema`, `rsi`, `macd`, `bollinger`, `atr`) and operators (`gt`, `lt`, `gte`, `lte`, `eq`, `crosses_above`, `crosses_below`):

```json
{
  "version": 1,
  "entry": {
    "logic": "AND",
    "conditions": [
      {
        "indicator": "sma",
        "params": { "period": 50 },
        "operator": "crosses_above",
        "against": { "indicator": "sma", "params": { "period": 200 } }
      }
    ]
  },
  "exit": {
    "logic": "AND",
    "conditions": [
      {
        "indicator": "sma",
        "params": { "period": 50 },
        "operator": "crosses_below",
        "against": { "indicator": "sma", "params": { "period": 200 } }
      }
    ]
  },
  "position_sizing": {
    "type": "fixed_fraction",
    "value": 0.95
  }
}
```

---

## Getting Started

### Prerequisites
* **Python** 3.11+
* **Node.js** 18+ (for the Vite React frontend)
* **PostgreSQL** with the `pgvector` extension enabled (`CREATE EXTENSION IF NOT EXISTS vector;`)
* **Redis** 6+

### 1. Clone & Configure Environment

```bash
git clone [https://github.com/u23ai105/QuantPilot-AI.git](https://github.com/u23ai105/QuantPilot-AI.git)
cd QuantPilot-AI
cp .env.example .env
```

Update `.env` with your credentials and configuration:

```env
APP_ENV=development
APP_NAME=QuantPilot AI
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/quantpilot
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
JWT_SECRET=change-me-to-a-strong-secret
LOG_LEVEL=INFO

# CORS & Security
CORS_ORIGINS=http://localhost:5173,[http://127.0.0.1:5173](http://127.0.0.1:5173)
RATE_LIMIT_ENABLED=true
METRICS_TOKEN=

# AI Providers
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.6-flash
LLM_PROVIDER=gemini
LLM_MODEL=
NVIDIA_API_KEY=
NVIDIA_BASE_URL=[https://integrate.api.nvidia.com/v1](https://integrate.api.nvidia.com/v1)

# Embeddings ("local" for FastEmbed BGE-base-en-v1.5 or "gemini")
EMBEDDING_PROVIDER=local
GEMINI_EMBEDDING_MODEL=models/gemini-embedding-001

# Frontend
VITE_API_BASE_URL=[http://127.0.0.1:8000/api/v1](http://127.0.0.1:8000/api/v1)
```

### 2. Backend Setup & Migrations

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Apply database migrations
alembic upgrade head

# Start the FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Start the Celery Worker

Run the worker subscribed to all three queues (`celery`, `backtest`, and `embedding`):

```bash
celery -A app.workers.celery_app:celery_app worker \
  --loglevel=info \
  -Q celery,backtest,embedding
```

*(Optional)* Monitor queues and task events locally with Flower:

```bash
celery -A app.workers.celery_app:celery_app flower --port=5555
```

### 4. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, register an account, ingest market data for a ticker (e.g., `AAPL`), upload a financial PDF, or start querying the Research Workspace.

---

## Docker & Low-Memory Deployment

Build and run the backend container using the included `Dockerfile`:

```bash
docker build -t quantpilot-ai .
docker run --env-file .env -p 8000:8000 quantpilot-ai
```

**Single-Process Embedded Worker Mode (512 MB RAM Tier):**
When `APP_ENV=production` or `RUN_WORKER=true`, `app/main.py` automatically starts an embedded Celery worker in a background daemon thread using `--pool=solo`. Sharing the Python memory space with FastAPI reduces combined memory consumption (from ~480 MB to ~210 MB), allowing the full API + worker stack to run reliably on constrained free-tier containers such as Render.

---

## Testing & Code Quality

```bash
# Run the async test suite (rate limiting is disabled automatically via root conftest.py)
pytest

# Run with branch coverage report
pytest --cov=app

# Lint and check import ordering with Ruff
ruff check .
```

---

## License

This project is licensed under the [MIT License](LICENSE).
