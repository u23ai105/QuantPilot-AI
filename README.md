<div align="center">
  <h1>🚀 QuantPilot AI</h1>
  <p><strong>Agentic Financial Research Assistant</strong></p>

  [![Status: Phase 7 (Product UI)](https://img.shields.io/badge/Status-Phase%207-blue.svg)](docs/phase-reports/)
  [![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
</div>

<br />

## 📖 Overview

**QuantPilot AI** is an agentic financial research assistant. A LangGraph tool-calling agent answers
questions about markets by calling deterministic Python finance code rather than reasoning about
numbers itself, and cites uploaded PDFs through a pgvector RAG pipeline. Backtests run asynchronously
on Celery. RAG quality is measured by a deterministic eval harness with no LLM judge.

The stack is a Python/FastAPI modular monolith plus a React/Vite SPA, backed by Postgres+pgvector and
Redis. Implementation has shipped through **Phase 7 (product UI)** — see
[`docs/phase-reports/`](docs/phase-reports/) for per-phase completion reports and
[`docs/architecture/`](docs/architecture/) for the design docs.

---

## ✨ Features

### 🧠 AI research assistant
*   **LangGraph agent** (`app/ai/`) — `START → agent_node → tool_node → agent_node → … → END`, with
    every tool exception captured as a `ToolMessage` so the agent recovers instead of crashing.
*   **Five tools**, all deterministic: `get_market_data`, `calculate_indicators`, `run_backtest`,
    `get_performance_metrics`, `search_documents`.
*   **Streaming chat** over SSE (`token`, `tool_start`, `tool_end`, `done`, `error` events), with
    durable conversation history in Postgres.
*   **RAG over PDFs** — upload a filing, it is chunked and embedded on the Celery `embedding` queue,
    then retrieved by cosine similarity from an HNSW pgvector index. Query embeddings are cached in
    Redis (keyed by a hash of the normalized query plus the model and dimensionality), so a repeated
    question costs no embedding quota; a cache miss or a Redis outage just recomputes.
*   **Eval harness** (`app/services/eval_service.py`) — scores answers deterministically: normalized
    string match, numeric match with tolerance, retrieval hit@k, and citation checks against the
    canonical `[Source: <filename>, Page: <n>]` format.

### 📈 Quantitative backtesting
*   **Declarative JSON strategies** — validated by `strategy_validator.py`, compiled into a
    `backtesting.py` strategy class by `strategy_interpreter.py`.
*   **Async execution** — submitting a backtest returns `202` immediately; the worker drives
    `QUEUED → RUNNING → COMPLETED|FAILED` with an atomic claim so redelivery is idempotent.
*   **Indicators**: SMA, EMA, RSI, MACD, Bollinger Bands, ATR (pure functions in `app/domain/`).
*   **Metrics**: total return, CAGR, volatility, Sharpe, Sortino, max drawdown, win rate.

### ⚙️ Platform
*   **Clean layering** — API → services → repositories → models, with `app/domain/` as a pure,
    dependency-free finance core shared by both the REST endpoints and the AI tools.
*   **Auth** — registration, bcrypt hashing, JWT bearer tokens; every resource read is
    ownership-scoped.
*   **Rate limiting** — Redis fixed-window budgets per caller on the endpoints that cost real
    resources (chat, backtest submission, ingestion, upload) plus login/register. Keyed by user id
    when a bearer token is present, client IP otherwise; responses carry `X-RateLimit-*` and a 429
    carries `Retry-After`. Fails open if Redis is down, since it guards cost, not access.
*   **Observability** — structlog with a per-request `X-Request-ID`, `GET /health` (liveness),
    `GET /ready` (checks Postgres + Redis), and `GET /metrics` in Prometheus exposition format:
    request counts and latency histograms labelled by *route template* (so ids never become label
    values), rate-limit rejections by rule, backtest submissions split into queued vs. idempotent
    replay, and query-embedding cache hits vs. misses. Open by default for a scraper on a private
    network; set `METRICS_TOKEN` to require a bearer token.

---

## 🛠️ Technology Stack

| Component | Technologies Used |
| :--- | :--- |
| **Backend API** | FastAPI, Python 3.11, SQLAlchemy 2 (async), Pydantic v2 |
| **Data** | PostgreSQL 16 + pgvector (HNSW), Alembic |
| **Background Tasks** | Celery, Redis |
| **AI / Machine Learning** | LangGraph, `gemini-2.0-flash`, `models/gemini-embedding-001` |
| **Quantitative** | backtesting.py, yfinance, pandas |
| **Frontend** | React 19, TypeScript, Vite, TanStack Query, Tailwind |
| **DevOps & Infra** | Docker Compose, Render, GitHub Actions, structlog, Ruff, Pytest |

---

## 🗺️ API surface

All routes are mounted under `/api/v1` and, apart from `auth`, require a bearer token.

| Area | Endpoints |
| :--- | :--- |
| `auth` | `POST /register`, `POST /login`, `GET /me` |
| `market-data` | `GET /tickers`, `GET /{symbol}`, ingest |
| `indicators` | `GET /{symbol}` (one or many indicators) |
| `strategies` | create, list, get |
| `backtests` | `POST /` (202), `GET /`, `GET /{id}`, `GET /{id}/results` |
| `conversations` | create, `POST /{id}/messages` (SSE), `GET /{id}/messages` |
| `documents` | upload (202), list, get, delete, `GET /{id}/search` |

Interactive docs at `http://localhost:8000/docs`.

---

## 💻 Local Development Setup

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Node 20+ (only for the frontend)

### 1. Environment Setup

```bash
git clone https://github.com/yourusername/quantpilot-ai.git
cd quantpilot-ai

python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
```

Set `GEMINI_API_KEY` in `.env`. The API boots without it — only the chat endpoint fails, by design.

### 2. Running the Infrastructure

Everything (API + worker + Postgres/pgvector + Redis):

```bash
docker compose up --build -d
```

Or just the datastores, if you want to run the API locally:

```bash
docker compose up db redis -d
```

### 3. Database Migrations

```bash
alembic upgrade head
```

### 4. Seed Market Data

```bash
python -m scripts.ingest_market_data
```

### 5. Run the API and worker locally

```bash
uvicorn app.main:app --reload
```

The worker must subscribe to all three queues or backtests and embeddings never run:

```bash
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2 --queues=celery,backtest,embedding
```

### 6. Frontend

```bash
npm --prefix frontend install
npm --prefix frontend run dev      # http://localhost:5173
```

### 7. Verification

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/metrics
```

### 8. Testing & Linting

The test suite is **not hermetic** — `tests/conftest.py` connects to a real Postgres with pgvector and
drops/recreates all tables per test, so `docker compose up db redis -d` must be running first.

```bash
ruff check .
ruff format --check .
pytest
pytest tests/test_auth.py::test_login_success    # single test
```

### 9. RAG evaluation

Seed the question set first, then run the harness (both make live LLM/embedding calls):

```bash
python scripts/seed_eval_questions.py
python scripts/run_eval.py
```

---

## 🚢 Deployment

`render.yaml` declares the deployment: a web service for the API (with
`releaseCommand: alembic upgrade head`), a Celery worker, managed Redis, and a static frontend build.
Secrets (`DATABASE_URL`, `GEMINI_API_KEY`, `JWT_SECRET`, `CORS_ORIGINS`) are set in the Render
dashboard, not committed.

---

## 📝 License

Intended to be MIT-licensed, but note that no `LICENSE` file is committed yet and `pyproject.toml`
declares no `license` field — add both before publishing.
