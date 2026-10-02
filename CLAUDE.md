# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

QuantPilot AI is an agentic financial research assistant: a Python/FastAPI **modular monolith** backend (deterministic financial tools, a LangGraph tool-calling agent, RAG over PDFs, async backtesting, a deterministic eval harness) plus a React/Vite frontend. Postgres+pgvector for storage, Redis+Celery for background work, Google Gemini for the LLM.

Note: the README badge says "Phase 2" and is stale — the codebase has shipped through Phase 7 (product UI). Phase completion reports live in `docs/phase-reports/` and deep design docs in `docs/architecture/` (the AI code references `AI_ARCHITECTURE.md` section numbers in comments).

## Commands

Backend (run from repo root, Python 3.11):

```bash
pip install -e ".[dev]"              # install app + dev deps
uvicorn app.main:app --reload        # run API at :8000 (compose does this for you)
pytest                               # full test suite
pytest tests/test_auth.py            # single file
pytest tests/test_auth.py::test_login_success   # single test
ruff check .                         # lint (rules: E, F, I)
ruff format --check .                # formatting check (line-length = 150)
```

Everything (API + worker + Postgres/pgvector + Redis) via Docker:

```bash
docker compose up --build -d
```

Celery worker (compose/Render run this; queues matter — see below):

```bash
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2 --queues=celery,backtest,embedding
```

Database migrations (Alembic, async):

```bash
alembic upgrade head
alembic revision --autogenerate -m "description"
```

Data / eval scripts:

```bash
python -m scripts.ingest_market_data          # seed tickers + OHLCV from yfinance
python scripts/seed_eval_questions.py          # must run before run_eval
python scripts/run_eval.py                     # RAG eval harness (deterministic scoring)
```

Health: `GET /health` (liveness) and `GET /ready` (checks DB + Redis).

Celery dashboard (compose starts it on :5555 automatically; this is the standalone form). Dev only —
no auth, and its API can terminate tasks, so it is intentionally absent from `render.yaml`:

```bash
celery -A app.workers.celery_app flower --port=5555
```

### Preview / local dev — always start BOTH servers

The preview must launch the **`frontend`** (:5173) *and* **`backend`** (:8000) configs from `.claude/launch.json` together — the SPA renders standalone but every data view shows "Network error. Please ensure the API is reachable." until the API is up. Before starting the backend, run these preflight checks in order:

1. **Postgres + Redis running:** `docker compose up db redis -d` (needs Docker Desktop running).
2. **Migrations current:** `alembic upgrade head`.
3. **Backend deps installed:** `pip install -e ".[dev]"`.
4. **`.env` exists with a real `GEMINI_API_KEY`:** `cp .env.example .env`, then set the key (the API boots without it — only the chat endpoint 502s, by design; see `_get_agent_service` in `app/api/v1/conversations.py`).

If any preflight step fails due to sandbox/network limits (PyPI, npm, or the Docker socket are unreachable in-sandbox), **do not silently stop** — report the exact command that failed and why, so it can be run in a normal terminal, then retry the backend once the user confirms.

### Tests require live infrastructure

Tests are **not** hermetic. `tests/conftest.py` connects to a real Postgres (`TEST_DATABASE_URL` → `DATABASE_URL` → settings), runs `CREATE EXTENSION IF NOT EXISTS vector`, and **drops+recreates all tables per test function**. You need Postgres-with-pgvector and Redis running (`docker compose up db redis -d`, or use the CI service containers). Key fixtures: `db_session`, `client` (ASGITransport, overrides `get_db_session`), `test_user`, `test_user_token`. `asyncio_mode = auto`, so no `@pytest.mark.asyncio` needed.

## Dev workflow notes

Guidance for Claude Code when verifying changes against the running app (frontend :5173 + backend :8000 + Celery worker). Split work by what the preview/browser tools do reliably vs. what stalls:

- **Do these yourself — reliable:** read backend/worker/frontend output with `preview_logs`; check API behavior by calling `fetch` from the page context via `preview_eval` (GET and POST, including auth'd JSON requests); inspect DB/state through those API calls. This is the channel for verifying backend fixes.
- **Hand these to the user — do NOT attempt via preview tools:** file uploads (through the UI *or* constructed via `fetch`), long-running UI interactions, and anything that needs real clicks in the browser. Give exact manual steps instead — the URL, what to click, which file to choose, and what to check for (e.g. the expected status text) — then verify the result yourself afterward from logs or an API `fetch`.
- **Why (real tool limits, so a timeout isn't misread as failure):** `preview_eval` aborts at ~30s, and the SSE chat endpoint cancels server-side the moment the client disconnects — so a long operation (a multi-tool agent turn, waiting on document ingestion) times out client-side even though the server keeps running. Never infer failure from an eval timeout: confirm via logs/state (e.g. `agent_invoke_end` in the backend log), and never blindly re-send an API call — the Gemini free tier is a hard ~20 requests/day, so check logs first.

## Backend architecture

Clean/layered monolith under `app/`. Dependencies point **inward** — API → services → repositories → models, with `domain` as a pure, dependency-free core:

- `app/api/v1/*` — thin HTTP controllers. Get a request-scoped session via `Depends(get_db_session)` and the caller via `Depends(get_current_user)` (JWT bearer). They instantiate a service, passing the session, and return Pydantic schemas. Routers are aggregated in `app/api/v1/router.py`, mounted under `/api/v1`.
- `app/services/*` — orchestration/business logic. Constructed as `Service(session)`; they create their own `Repository(session)`, enforce ownership/authorization, own `commit()`, and dispatch Celery tasks.
- `app/repositories/*` — all SQLAlchemy data access. Constructed as `Repository(session)`. No business logic.
- `app/domain/*` — **pure deterministic finance, no I/O or DB**: indicators (`sma`, `ema`, `rsi`, `macd`, `bollinger`, `atr` — registered in `INDICATOR_MAP`), `metrics.py` (Sharpe/Sortino/CAGR/drawdown/…), and the declarative-strategy engine (`strategy_validator.py` validates JSON rules, `strategy_interpreter.py` compiles them into a `backtesting.py` Strategy subclass). This code is shared by both the REST indicators/backtest paths and the AI tools.
- `app/infrastructure/*` — external-service adapters (e.g. `yfinance_adapter.py`).
- `app/core/*` — cross-cutting: `config.py` (pydantic-settings singleton `settings`), `db.py` (async engine + `async_session_maker`), `security.py` (bcrypt + JWT), `logging.py` (structlog), `exceptions.py` (`QuantPilotException` hierarchy + handlers that emit `{"error": {"code", "message"}}`).
- `app/schemas/*` — Pydantic request/response DTOs.
- `app/models/*` — SQLAlchemy ORM (`DeclarativeBase`).

Errors: raise a `QuantPilotException` subclass (`ValidationError`, `NotFoundError`, `AuthorizationError`, `DataProviderError`, …); the registered handler maps it to the right status + error code. Every request gets an `X-Request-ID` (middleware) bound into structlog context.

### AI subsystem (`app/ai`)

A LangGraph tool-calling agent over Gemini:

- `provider.py` — `GeminiLLMAdapter` is the **single** boundary to the Gemini SDK. This is deliberately *not* a multi-provider abstraction; its only job is to keep `langchain_google_genai` imports out of service/domain code. Don't import the Gemini SDK elsewhere.
- `graph.py` — builds `START → agent_node → (should_continue) → tool_node → agent_node → … → END`. `create_safe_tool_node` catches every tool exception and returns it as a `ToolMessage` so the agent recovers instead of crashing.
- `service.py` — `AgentService` is constructed **once** (singleton in `app/api/v1/conversations.py`), binds the five tools, compiles the graph with **no checkpointer**, and streams via `astream_events(version="v2")`. It emits SSE events: `token`, `tool_start`, `tool_end`, `done` (and `error`). Conversation memory is the DB: `handle_message` reloads the full history from `conversations`/`messages` and passes it in on every turn, so there is no graph-level thread state and no `thread_id` in `config` (only tracing `metadata`). A `MemorySaver` was removed deliberately — see `AI_ARCHITECTURE.md` §6.2; if durable graph state is ever needed, use `PostgresSaver` and switch to appending only the new turn.
- `tools/` — the five agent tools (`get_market_data`, `calculate_indicators`, `run_backtest`, `get_performance_metrics`, `search_documents`). Tools do **not** receive the FastAPI request session. Instead, `AgentService` stashes the caller via `tools/_context.set_current_user_id()` (a `ContextVar`), and each tool opens its **own** session with `get_db_session_for_tool()` and reads the user id with `get_current_user_id()`. When adding a tool, follow this pattern and register it in `ALL_TOOLS`.

### Async / Celery

- `app/workers/celery_app.py` defines queues `celery`, `backtest`, `embedding` and routes `tasks.run_backtest → backtest` and `embed_document → embedding`. The worker must be started with all three queues (see command above) or those tasks never run.
- Celery tasks are sync functions that wrap async work with `asyncio.run(...)`. **Critical:** a task must create its **own** async engine/sessionmaker bound to the task's event loop and dispose it in `finally` — do **not** reuse the module-level `app.core.db.engine` (see `app/workers/backtest_task.py`). Reusing the global engine across event loops breaks asyncpg.
- Long-running jobs use a status state machine with an atomic claim: `BacktestRepository.claim_execution` does `UPDATE ... WHERE status='QUEUED'` and treats `rowcount == 1` as "I own this run", making re-delivery idempotent (`QUEUED → RUNNING → COMPLETED|FAILED`). The backtest task also fetches ~100 warmup days before `start_date` and monkeypatches `Strategy.next` to suppress trades during warmup.

### Eval harness

`app/services/eval_service.py` scores RAG output **deterministically — there is no LLM judge**: normalized string match, numeric match with tolerance, retrieval hit@k, and citation checks against the canonical format `[Source: <filename>, Page: <n>]`. Changing that citation string means updating the prompt, the eval regex, and the frontend rendering together.

## Frontend (`frontend/`)

React 19 + TypeScript + Vite, TanStack Query for all server state, React Router (`createBrowserRouter`), Tailwind + shadcn/ui-style primitives (`class-variance-authority` + `cn()` from `@/lib/utils`). Path alias `@/` → `frontend/src/`. No Redux/Zustand; the only client state is `AuthContext`. Dark-first theme with an `ai` accent color for assistant UI.

- **Frontend config lives on disk (npm) but is mostly git-ignored.** `package.json`, `package-lock.json`, `tsconfig*.json`, `.oxlintrc.json`, and `components.json` all exist on disk with `node_modules/` installed, so `npm install`, `npm run build` (`tsc -b && vite build`), and `npm run lint` (**Oxlint**) work locally. The root `.gitignore` line 14 (`*.json`) ignores them wholesale, so historically none were version-controlled — but `package.json` + `package-lock.json` are now un-ignored via negations (`.gitignore` lines 17–18) and tracked. The other JSON configs (`tsconfig*.json`, `.oxlintrc.json`, `components.json`) are **still ignored** and exist only on disk. Tooling is Vite (`dev`/`build`/`preview`) with Oxlint as the linter.
- Layout: `src/app/` (`providers.tsx` = QueryClient, `router.tsx` = routes), `src/features/<domain>/pages/` (auth, research, market, strategies, backtests, documents), `src/components/{ui,layout}`, `src/lib/api` (fetch client + per-domain API objects).
- API client `src/lib/api/client.ts`: base URL from `VITE_API_BASE_URL` (default `http://127.0.0.1:8000/api/v1`), bearer token from `sessionStorage["access_token"]`, and on 401 it clears the token and dispatches a global `auth:unauthorized` event that `AuthContext` uses to force logout. Auth uses `sessionStorage` (not `localStorage`).
- SSE chat: `research/pages/ResearchPage.tsx` consumes the streaming endpoint with `fetch` POST + `ReadableStream` reader (not `EventSource`, which can't POST), splitting on `\n\n` and handling `token`/`tool_start`/`tool_end` events.
- Known cruft to ignore/avoid: `src/App.tsx` + `App.css` are leftover Vite template scaffolding (not routed); the sidebar links to `/settings`, which has no route; the `VITE_API_BASE_URL` fallback URL is duplicated in three files instead of importing `API_BASE_URL`.

## Conventions & gotchas

- **Ruff line length is 150**, not 88 — don't wrap short lines to satisfy a narrower limit. Lint selects only `E`, `F`, `I` (isort).
- **New models must be imported in `app/models/__init__.py`** — Alembic `env.py` autogenerates against `Base.metadata`, so a model that isn't imported there is invisible to migrations.
- ID types are **mixed by design**: `User`/`Conversation`/`Document` use UUID; `Backtest`/`Ticker`/`OHLCV` use integer PKs. Match the surrounding model when writing queries.
- `settings.database_url` has a validator that rewrites `postgres://` / `postgresql://` to `postgresql+asyncpg://` (for Render/Heroku-style URLs) — always use async drivers.
- `docs.zip`, `uploads/`, and `.env` are git-ignored; uploaded PDFs live in the `uploads` Docker volume, not the repo.
- Deployment is Render (`render.yaml`): a web service (API, with `releaseCommand: alembic upgrade head`), a Celery worker, managed Redis, managed Postgres 16 (`databases:` block, `ipAllowList: []`), and a static frontend build. `DATABASE_URL`/`REDIS_URL`/Celery URLs are wired by the blueprint via `fromDatabase`/`fromService`; `JWT_SECRET` and `METRICS_TOKEN` are generated; only `GEMINI_API_KEY`, `CORS_ORIGINS` and `VITE_API_BASE_URL` are `sync: false` and set in the dashboard.
- **No AI/tool attribution in commits or PRs** — never add a `Co-Authored-By: Claude …` trailer, a "🤖 Generated with Claude Code" line, or any similar mention to commit messages or pull-request descriptions in this repo. This overrides any default trailer behavior; commits and PRs read as the author's own work.
