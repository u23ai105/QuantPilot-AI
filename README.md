<div align="center">
  <h1>🚀 QuantPilot AI</h1>
  <p><strong>Agentic Financial Research Assistant</strong></p>

  [![CI](https://github.com/u23ai105/QuantPilot-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/u23ai105/QuantPilot-AI/actions/workflows/ci.yml)
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
    network; set `METRICS_TOKEN` to require a bearer token. Celery has its own dashboard — Flower,
    at `:5555` under compose — for queue depth and task history.

---

## 🛠️ Technology Stack

| Component | Technologies Used |
| :--- | :--- |
| **Backend API** | FastAPI, Python 3.11, SQLAlchemy 2 (async), Pydantic v2 |
| **Data** | PostgreSQL 16 + pgvector (HNSW), Alembic |
| **Background Tasks** | Celery, Redis |
| **AI / Machine Learning** | LangGraph, `gemini-3.6-flash`, `models/gemini-embedding-001` |
| **Quantitative** | backtesting.py, yfinance, pandas |
| **Frontend** | React 19, TypeScript, Vite, TanStack Query, Tailwind |
| **DevOps & Infra** | Docker Compose, Render, GitHub Actions, structlog, Ruff, Pytest |

---

## 🤖 LLM Providers

- **Gemini (default):** `gemini-3.6-flash` is the default model.
- **NVIDIA NIM (optional):** Selected with `LLM_PROVIDER=nim`, `LLM_MODEL`, and `NVIDIA_API_KEY`.
- **Embeddings:** Stay on Gemini (`models/gemini-embedding-001`).
- **Verified NIM model:** `nvidia/nemotron-3-ultra-550b-a55b`. See [`app/ai/model_registry.py`](app/ai/model_registry.py) for unverified candidates.

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
git clone https://github.com/u23ai105/QuantPilot-AI.git
cd QuantPilot-AI

python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
```

Set `GEMINI_API_KEY` in `.env`. The API boots without it — only the chat endpoint fails, by design.

### 2. Running the Infrastructure

All five services in `docker-compose.yml` — API, worker, Postgres/pgvector, Redis, and Flower (the
dev-only Celery dashboard, see step 8):

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

### 8. Watching the queues (Flower)

`docker compose up` already starts Flower on <http://localhost:5555> — queue depth per queue, task
history with arguments and runtimes, and worker heartbeats. It is how you tell "the backtest is
slow" apart from "nothing is consuming the `backtest` queue".

Running the worker outside Docker instead? Point Flower at the same broker:

```bash
celery -A app.workers.celery_app flower --port=5555
```

Flower reads Celery *task events*, which `app/workers/celery_app.py` turns on
(`worker_send_task_events`, `task_send_sent_event`). Without them the dashboard lists workers but
no tasks.

It is deliberately development-only and absent from `render.yaml`: the dashboard has no
authentication, its API can revoke and terminate tasks, and task arguments are shown in plain text.

### 9. Testing & Linting

The test suite is **not hermetic** — `tests/conftest.py` connects to a real Postgres with pgvector and
drops/recreates all tables per test, so `docker compose up db redis -d` must be running first.

It also uses a **separate database named `quantpilot_test`** (derived from `DATABASE_URL` by
suffixing the database name, or set explicitly via `TEST_DATABASE_URL`) so the suite never drops your
development schema. Create it once, with the `vector` extension, before running `pytest`:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE quantpilot_test;"'
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d quantpilot_test -c "CREATE EXTENSION IF NOT EXISTS vector;"'
```

```bash
ruff check .
ruff format --check .
pytest
pytest tests/test_auth.py::test_login_success    # single test
```

### 10. RAG evaluation

Seed the question set first, then run the harness (both make live LLM/embedding calls):

```bash
python scripts/seed_eval_questions.py
python scripts/run_eval.py
```

---

## 🚢 Deployment

`render.yaml` declares the whole deployment: a web service for the API (with
`releaseCommand: alembic upgrade head`), a Celery worker, managed Redis, managed Postgres, and a
static frontend build. Postgres and Redis are provisioned by the blueprint, so `DATABASE_URL`,
`REDIS_URL` and the Celery broker/backend URLs are wired automatically — `JWT_SECRET` and
`METRICS_TOKEN` are generated, and only the genuinely external values (`GEMINI_API_KEY`,
`CORS_ORIGINS`, `VITE_API_BASE_URL`) have to be filled in from the Render dashboard.

The database is pinned to Postgres 16 to match the local `pgvector/pgvector:pg16` image, and the
`vector` extension is created by the first migration rather than by hand.

---

## 📚 Documentation

- [`docs/PROGRAM.md`](docs/PROGRAM.md) — Technical Program Management overview: scope, team ownership, milestones, RAID log, key architectural trade-offs, and quality gates.
- [`docs/architecture/`](docs/architecture/) — High-Level Design (HLD), Low-Level Design (LLD), component architecture, and ADRs.
- [`docs/phase-reports/`](docs/phase-reports/) — Implementation completion reports across delivery milestones.

---

## 👥 Team

Built by Muzammil and Rajkumar.

| Area | Owner |
| :--- | :--- |
| API / Auth | Muzammil, Rajkumar |
| Database and migrations | Muzammil, Rajkumar |
| Backtesting | Muzammil, Rajkumar |
| RAG / Agent | Muzammil, Rajkumar |
| CI / Testing | Muzammil, Rajkumar |
| Docs | Muzammil, Rajkumar |

---

## 📝 License

MIT — see [`LICENSE`](LICENSE).
