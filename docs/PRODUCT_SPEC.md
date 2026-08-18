# QuantPilot AI — Final Locked Build Plan
### SDE + GenAI Interview Project (Quant is the domain, not the skill)

---

## 0. The One Rule

> **Every module either teaches you SDE, teaches you GenAI, or directly supports a module that does. If it does neither, it does not get built right now — no guilt.**

You are not building a fintech product. You are building **two deep, defensible skill demonstrations** that happen to live inside a finance-flavored shell. If a feature's main value is "looks impressive on a screenshot" rather than "I can defend this for 15 minutes under questioning," it does not belong in the build.

This document locks scope to exactly what you should build, in what order, to what standard, with what you say about it in an interview.

---

## 1. The One-Sentence Pitch (what you're building toward)

> "I built an agentic financial research assistant — a FastAPI/PostgreSQL backend with a LangGraph agent that calls deterministic Python tools instead of hallucinating numbers, RAG over financial PDFs with page-level citations, async backtesting via Celery/Redis, and an evaluation harness that measures retrieval accuracy instead of eyeballing outputs."

Every clause in that sentence maps to one module below. Nothing in the locked scope exists outside that sentence.

---

## 2. Locked Scope — Everything You Are Building

### 2A. SDE Foundation

| Piece | Detail |
|---|---|
| API framework | FastAPI, modular monolith: `api/` → `service/` → `repository/` layering |
| Database | PostgreSQL + SQLAlchemy (async) + Alembic migrations |
| Auth | JWT — register, login, protected routes, password hashing (passlib/bcrypt) |
| Async jobs | Redis + Celery — backtests and embedding runs execute as background tasks |
| Containerization | Docker Compose: `api`, `worker`, `db`, `redis` |
| Testing | Pytest — unit tests for calculations, integration tests for API flows |
| CI | GitHub Actions — lint (ruff) + test on every push |
| Validation | Pydantic schemas on every request/response boundary |
| Docs | FastAPI's OpenAPI, filled in properly — examples, response models, tags |
| Logging | Structured logging (structlog or stdlib + JSON formatter), consistent error handler middleware |

### 2B. Quant Layer — thin, in service of the AI, not a product

| Piece | Detail |
|---|---|
| Market data | One free-tier source (yfinance) for a **fixed universe of 30–50 tickers** |
| Storage | OHLCV in Postgres, one table, indexed on `(ticker_id, date)` |
| Indicators | SMA, EMA, RSI, MACD, Bollinger, ATR — via pandas/numpy |
| Strategy format | One declarative JSON rule format only (no visual builder, no separate Python-strategy mode) |
| Backtest engine | **One** library — `backtesting.py` (recommended; see §3 below) |
| Metrics | Total return, CAGR, volatility, Sharpe, Sortino, max drawdown, win rate |
| Execution | Every backtest runs as a Celery task, not inline in the request |

### 2C. GenAI Centerpiece — this is what should shine

| Piece | Detail |
|---|---|
| Agent framework | LangGraph — real tool-calling graph, not one LLM call |
| Tools | 5 tools, see §5 |
| Core principle | The LLM never computes a number — it calls a tool, the tool returns ground truth, the LLM explains it |
| RAG | One document type (10-K/annual report PDFs) → PyMuPDF parse → chunk → embed → pgvector → retrieve → cited answers |
| Structured output | Tool schemas validated, streaming responses, basic conversation state |
| Eval harness | 15–20 question/expected-citation pairs + a scoring script for retrieval + citation accuracy |

**If you build only what's in 2A + 2B + 2C, you are done.** Not "done for now" — done. That is a complete, interview-ready project. Everything past this point in the doc is either *how* to build the above, or an explicit list of what you are *not* building.

---

## 3. Backtest Engine Choice — decide this once, don't revisit it

Use **`backtesting.py`**, not `vectorbt`.

- `vectorbt`'s API is unusual and will cost you real days just to learn its indexing/vectorization conventions.
- `backtesting.py` gets you a correct, working backtest loop fast — the time you save goes into the agent and RAG layer, which is where your actual differentiation lives.
- You can defend "I chose the simpler library because my differentiation is in the AI layer, not backtest engine internals" — that's a *good* interview answer about judgment, not a weakness.

---

## 4. Database Schema (lock this before writing code)

```
users            (id, email, hashed_password, created_at)

tickers          (id, symbol, name, sector)

ohlcv            (id, ticker_id FK, date, open, high, low, close, volume)
                 UNIQUE(ticker_id, date)

strategies       (id, user_id FK, name, rules_json, version, created_at)

backtests        (id, strategy_id FK, ticker_id FK, start_date, end_date,
                  initial_capital, fees, status, celery_task_id, created_at)

backtest_results (id, backtest_id FK, total_return, cagr, volatility, sharpe,
                  sortino, max_drawdown, win_rate, equity_curve_json, trades_json)

documents        (id, user_id FK, filename, uploaded_at, page_count)

document_chunks  (id, document_id FK, page_number, chunk_text, embedding vector(768))

conversations    (id, user_id FK, created_at)

messages         (id, conversation_id FK, role, content, tool_calls_json, created_at)

eval_questions   (id, question, expected_answer, expected_doc_id, expected_page)

eval_runs        (id, run_at, question_id FK, retrieval_hit, citation_correct, answer_score)
```

This is the whole schema. Resist adding tables for anything in the cut list (§9) — a table you build "just in case" is scope creep with extra steps.

---

## 5. Agent Tool Spec (this is the part interviewers will drill hardest)

```python
get_market_data(symbol: str, start: date, end: date) -> list[OHLCVBar]
calculate_indicators(symbol: str, indicator: str, params: dict) -> list[float]
run_backtest(strategy_id: int, symbol: str, start: date, end: date) -> BacktestHandle
get_performance_metrics(backtest_id: int) -> MetricsDict
search_documents(query: str, document_id: int | None) -> list[ChunkWithCitation]
```

**Graph shape (LangGraph):**

```
START → agent_node (LLM bound to tools)
           │
           ├─ tool calls requested? ──yes──→ tool_node → back to agent_node
           │
           no
           ↓
          END (final answer, streamed)
```

State/memory: use a checkpointer (start with `MemorySaver`, upgrade to Postgres-backed if time allows) so a conversation can reference earlier turns — this is your answer to "how does your agent maintain context."

**Failure-mode handling to actually implement, not just talk about:**
- Tool raises an exception → caught, returned to the LLM as a tool-error message, not a crash
- `run_backtest` is slow (it's async under the hood) → the tool either polls Celery with a timeout or returns a handle the agent explains is "still running"
- Retrieval returns nothing → the agent says so explicitly rather than inventing an answer

---

## 6. RAG Pipeline Detail

```
PDF upload → PyMuPDF text extraction (per page)
           → chunk (e.g. ~500 tokens, page boundary respected)
           → embed each chunk (one embedding model, don't abstract over providers)
           → store in pgvector with (document_id, page_number, chunk_text, embedding)
           → on query: embed query → cosine similarity search → top-k chunks
           → LLM answers using only retrieved chunks, cites (document, page) per claim
```

Keep it to **one document type**. Adding invoices, research notes, CSVs, etc. multiplies parsing edge cases for a "nice to have" that doesn't teach you anything new about RAG mechanics.

---

## 7. Eval Harness Detail (small effort, disproportionate interview value)

1. Build 15–20 question/answer pairs against your uploaded documents, each with a known correct `(document_id, page_number)`.
2. Script runs each question through retrieval, checks:
   - **Retrieval hit@k** — was the correct chunk in the top-k retrieved?
   - **Citation accuracy** — did the final answer cite the correct page?
   - **Answer quality** — keyword/heuristic check is enough; LLM-as-judge is a stretch add if time allows.
3. Output a simple table/report (even a printed dataframe is fine) you can show in an interview.

This single artifact is the thing that separates "I called an API" from "I understand how to validate an AI system." Almost nobody at your level builds this — it's worth more than three extra features.

---

## 8. Suggested Build Order (phases, not calendar dates)

| Phase | What you build | Definition of done | Rough effort |
|---|---|---|---|
| 0 | Repo scaffold, decide LLM provider, decide `backtesting.py`, README skeleton | `docker compose up` boots an empty FastAPI app | 2–3 days |
| 1 | FastAPI + Postgres + Alembic + JWT auth + Docker Compose + first CI + first tests | Can register/login a user, CI runs green on push | 1–2 weeks |
| 2 | Market data ingestion + OHLCV storage + indicators + unit tests | Indicators match hand-computed values on a known series | ~1 week |
| 3 | Strategy JSON format + backtest engine + Celery task + metrics + known-answer tests | A hand-computable strategy's Sharpe matches your backtest output | 1.5–2 weeks |
| 4 | LangGraph agent + 4 calculation tools + chat endpoint + streaming | Agent answers "what's the Sharpe of X" by calling tools, never inventing the number | 1.5–2 weeks |
| 5 | RAG: upload → chunk → embed → pgvector → `search_documents` tool → citations | Agent answers a 10-K question with a correct page citation | 1.5–2 weeks |
| 6 | Eval harness: Q/A set + scoring script | Script prints hit-rate and citation accuracy across your 15–20 questions | 3–5 days |
| 7 | Polish: logging, error-handling edge cases, README + architecture diagram, demo video/screenshots | You could hand this repo to a stranger and they'd understand it in 10 minutes | ~1 week |

**Total core build: roughly 8–11 weeks part-time**, alongside coursework. That's realistic for one person going deep rather than wide.

**Do not start Phase 8 (below) until Phase 0–7 is done and you've dry-run the interview-readiness checklist in §10 against every module.**

---

## 9. Explicit Cut List — you are not building these right now

Say this list out loud to yourself once so you stop feeling like you're "missing" something:

| Cut | Why |
|---|---|
| Portfolio optimization (min-variance, max-Sharpe, efficient frontier) | Real math, real dependency, but teaches you neither SDE nor GenAI — and it's the exact feature an interviewer will ask you to derive from scratch if you list it |
| Second "Python strategy" mode | One well-built strategy format beats two half-built ones |
| Screener | Pure filter/UI feature, no new skill signal |
| Full news pipeline (ingestion, dedup, ticker extraction, custom sentiment) | Data-engineering effort with poor ROI against your stated goals — if you add news at all later, it's a single agent tool that calls a news API inline, nothing more |
| Watchlists | Trivial CRUD — never mention it as a "feature" even if you build it for UI filler |
| Paper trading | Stateful, but pure domain logic — teaches nothing Phase 1–7 doesn't already cover |
| Visual strategy builder UI | Redundant once you have the JSON format |
| Institutional-grade risk engine (VaR/CVaR/correlation matrix) | High effort, low interview value unless you're specifically targeting quant roles |
| Frontend (beyond a thin demo shell) | Not your stated focus — a 3-screen Streamlit app is enough to demo; do not build a polished React app right now |
| Multi-provider LLM abstraction, custom vector DB, Kafka, Kubernetes, microservices | Already correctly identified as out of scope — keep them cut |

If, after Phase 7, you have real time left *and* every module already passes the §10 checklist, the only things worth even considering are (in this order): a thin 3–4 screen demo frontend, then basic portfolio P&L tracking. Nothing else on this list.

---

## 10. Interview-Readiness Checklist

Before any feature goes on your resume, you need a clean answer — no notes — to all of these:

1. What happens if a tool call fails mid-agent-run? How do you handle it?
2. How do you know your RAG retrieval is actually good, not just "it looked fine when I tried it"?
3. What would happen if two backtest requests for the same strategy ran concurrently — any race conditions?
4. Why Celery over a background thread? Why Redis as the broker over something else?
5. Walk me through one full request end-to-end: HTTP call → FastAPI → service → repository → Postgres → response.
6. What's your test strategy — what's unit-tested vs. integration-tested, and why?
7. If this had to scale to 10,000 users, what's the first thing that breaks?
8. Why did you choose `backtesting.py` over `vectorbt`? What would you lose/gain switching?
9. How do you know the LLM isn't just making up the numbers it reports?
10. What's in your eval set, and what does a failing case actually look like?

**If you can't answer one for a given feature, that feature isn't a resume bullet yet.** Keep building depth there before touching the next module.

---

## 11. Resume Bullets (only write these once true)

- Built an agentic financial research assistant using LangGraph with real tool-calling, where the LLM never computes a number itself — all calculations run through deterministic Python tools.
- Implemented RAG over financial PDFs (PyMuPDF → chunking → pgvector) with page-level citation grounding, validated by a custom evaluation harness measuring retrieval and citation accuracy.
- Designed a modular-monolith FastAPI backend (PostgreSQL, SQLAlchemy, Alembic, JWT auth) with async task processing via Celery/Redis for long-running backtests.
- Built a full CI/CD pipeline (Docker Compose, GitHub Actions, Pytest) with unit tests validating quant calculations against hand-computed known-answer cases.

---

## 12. Tech Stack — final, no ambiguity left

| Layer | Use |
|---|---|
| Backend | FastAPI, SQLAlchemy (async), Alembic, Pydantic |
| DB | PostgreSQL + pgvector |
| Async | Redis + Celery |
| AI | LangGraph, one LLM provider only, PyMuPDF |
| Backtesting | `backtesting.py` |
| Infra | Docker Compose, GitHub Actions |
| Testing | Pytest |
| Frontend (only if time remains) | Streamlit or a 3–4 screen React shell |

Nothing outside this table gets added without going back to §0 and asking whether it teaches SDE, teaches GenAI, or supports a module that does.