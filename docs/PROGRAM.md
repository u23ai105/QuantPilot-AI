# QuantPilot AI — Program Management Overview

**Program:** QuantPilot AI  
**Role:** Agentic Financial Research Assistant  
**Team:** 2-Person Engineering Team (Muzammil and Rajkumar)  
**Target Reviewer:** Technical Program Management (TPM) Internship Reviewer  

---

## 1. Goal and Scope

### What Was Built
QuantPilot AI is an agentic financial research assistant built as a clean modular monolith (FastAPI backend + React 19/Vite frontend) backed by PostgreSQL 16 with pgvector and Redis 7. It bridges generative AI and quantitative finance:
- **Agentic AI Centerpiece:** A LangGraph tool-calling agent orchestrating 5 deterministic tools (`get_market_data`, `calculate_indicators`, `run_backtest`, `get_performance_metrics`, `search_documents`). The LLM is restricted to planning, routing, and synthesis; numerical computation is strictly delegated to deterministic domain code.
- **RAG Subsystem:** Ingestion of 10-K/annual-report PDFs via PyMuPDF, sentence-greedy chunking strictly respecting page boundaries with zero overlap for precise attribution, asymmetric Gemini embeddings (`models/gemini-embedding-001`, 768 dimensions), cosine similarity retrieval via an HNSW vector index (`m=16, ef_construction=64`), and Redis query embedding caching.
- **Quantitative Engine & Backtesting:** Pure domain calculations for 6 technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands, ATR) and 8 performance metrics (Total Return, CAGR, Volatility, Sharpe, Sortino, Max Drawdown, Win Rate, Total Trades). Declarative JSON strategy DSL compiler (whitelist validator + closure-based interpreter over `backtesting.py`). Asynchronous job execution via Celery 5 with atomic status claims and idempotency keys.
- **Production Readiness & Observability:** 12 PostgreSQL tables managed via async Alembic migrations, JWT authentication with bcrypt hashing, Redis fixed-window rate limiting (fail-open), Prometheus metrics (`/metrics`) with bounded route cardinality, and a 5-service local Docker Compose stack (`api`, `worker`, `db`, `redis`, `flower`).

### Explicitly Out of Scope
To maintain engineering depth over superficial breadth, the following were explicitly excluded by architectural policy:
- Portfolio optimization (Markowitz efficient frontier, Black-Litterman, risk-parity).
- Visual drag-and-drop strategy builders or arbitrary Python script execution (preventing remote code execution).
- Stock screeners, watchlists, paper trading, news stream ingestion, or sentiment scrapers.
- Institutional trade routing, FIX protocol, HFT infrastructure, live brokerage execution, or real-money trading.
- Multi-provider LLM abstraction layers (beyond the primary adapter and optional NIM toggle), Kafka, Kubernetes, or microservice decomposition.

---

## 2. Team and Ownership

*Note: Roles are tracked at the module level. Per program tracking rules, specific personal assignments remain unassigned in documentation pending owner confirmation.*

| Area | Owner | Reviewer |
| :--- | :--- | :--- |
| **API & Authentication** (FastAPI, JWT, endpoints, rate limiting) | Muzammil, Rajkumar | - |
| **Database & Migrations** (PostgreSQL, Alembic, pgvector, HNSW) | Muzammil, Rajkumar | - |
| **Backtesting & Quant** (Strategy DSL, backtesting.py, Celery, metrics) | Muzammil, Rajkumar | - |
| **RAG & Agent** (LangGraph, PyMuPDF, embeddings, caching, prompts) | Muzammil, Rajkumar | - |
| **CI & Testing** (GitHub Actions, Pytest suite, test DB harness, Ruff) | Muzammil, Rajkumar | - |
| **Documentation** (HLD, LLD, ADRs, phase reports, runbooks) | Muzammil, Rajkumar | - |

---

## 3. Milestones

The project was executed across 7 sequenced phases, each locked to rigorous exit criteria:

| Phase | Deliverable | Exit Criterion | Report Link |
| :--- | :--- | :--- | :--- |
| **0. Foundation** | Repository scaffold, async SQLAlchemy, Alembic, Celery config, Docker Compose | Clean service startup; Alembic asyncpg setup verified; Postgres & Redis healthy | [PHASE-0.md](phase-reports/PHASE-0.md) |
| **1. SDE Foundation** | User auth (register, login, `/me`), JWT tokens, password hashing (bcrypt), UserRepository & AuthService | 8/8 pytest passing; Ruff clean; migrations applied cleanly; secure password hashing | [PHASE-1.md](phase-reports/PHASE-1.md) |
| **2. Market Data** | Tickers, OHLCV schema, yfinance adapter (35 tickers), 6 technical indicators, lookback warmup validation | Indicator known-answer tests pass; Alembic migration clean; 0/N trading days warmup validation fails loud | [PHASE-2.md](phase-reports/PHASE-2.md) |
| **3. Backtesting** | JSON strategy validator/interpreter, Celery backtest task, atomic CAS claim (`QUEUED` → `RUNNING`), MetricsCalculator | 30/30 pytest passing; Celery worker consumes queues; task-local async engine lifecycle verified | [PHASE-3.md](phase-reports/PHASE-3.md) |
| **4. AI Agent** | LangGraph StateGraph, tool-calling loop, safe tool node exception catching, SSE streaming (`token`, `tool_*`, `done`) | 45/45 pytest passing; streaming SSE wire contract verified; tool error handling verified | [PHASE-4.md](phase-reports/PHASE-4.md) |
| **5. RAG Pipeline** | PyMuPDF extraction, page-boundary chunking, asymmetric Gemini embeddings, pgvector HNSW search, upload security | 52/52 pytest passing; upload vulnerability tests pass; user-scoped vector search isolated | [PHASE-5.md](phase-reports/PHASE-5.md) |
| **6. Evaluation** | Deterministic EvalService (Hit@5, Citation Accuracy, Canonical Format, Numeric Match 5% tol), 15 benchmark questions | 15/15 retrieval hit@5; eval scorer unit tests pass; results persisted to `eval_runs` | [PHASE-6.md](phase-reports/PHASE-6.md) |

*(Note: Phase 7 delivered the React 19 UI, Recharts equity curve, Redis rate limiting, Prometheus metrics, and Flower Celery dashboard as recorded in [PROGRESS.md](../PROGRESS.md); no standalone `PHASE-7.md` file exists in `docs/phase-reports/`).*

---

## 4. RAID Log (Risks, Assumptions, Issues, Dependencies)

| Type | Item | Mitigation / Resolution | Status |
| :--- | :--- | :--- | :--- |
| **Dependency** | Gemini LLM and embedding rate/quota constraints | Implemented Redis query embedding cache (`CachedQueryEmbedder`, 24h TTL) and per-caller fixed-window rate limiting | Closed (Active mitigation) |
| **Risk** | Redis outage blocking application traffic | Cache and rate limiter fail open: on Redis error, queries bypass cache and rate limiter logs warning without raising 429; `/ready` reports degradation | Closed (Active mitigation) |
| **Issue (resolved)** | Worker not consuming all queues, causing backtest and embedding tasks to stall indefinitely | Root cause identified: Celery worker defaulted to `celery` queue only. Fixed by explicitly declaring `--queues=celery,backtest,embedding` in Compose and Render configs | Resolved |
| **Issue (resolved)** | Gemini streaming chunk normalization, MissingGreenlet in backtest service, wrong embedding model name | Implemented chunk normalization for list-shaped tokens; extracted plain IDs before post-rollback queries; updated embedding model to `models/gemini-embedding-001` | Resolved |
| **Risk** | Flower Celery dashboard has no built-in authentication | Container is restricted to development environment (`docker-compose.yml`); explicitly excluded from production `render.yaml` | Closed (Active mitigation) |
| **Dependency** | Upstream market data quality via yfinance | Constrained to fixed 35-ticker universe; adapter normalizes fields, checks data sanity (`high >= low`, `volume >= 0`), and strips NaN rows | Closed (Active mitigation) |
| **Issue (resolved)** | Fresh test runs failed because `quantpilot_test` database was absent | Added setup commands to README §9; isolated test configuration via `_default_test_database_url` to prevent dropping dev schema | Resolved |
| **Issue (resolved)** | Google shut down default model `gemini-2.0-flash` on June 1, 2026 | Updated default model to `gemini-3.6-flash` across `config.py`, documentation, and deployment blueprints | Resolved |
| **Dependency (open)** | Gemini free tier allows ~20 calls/day, bottlenecking live evaluation runs | Mitigated by introducing optional NVIDIA NIM provider behind config switch (`LLM_PROVIDER=nim`) | Open (Mitigated) |
| **Issue (open)** | Evaluation on Nemotron 3 Ultra hit 3/15 provider overload errors (12/15 succeeded, 15/15 retrieval hit@5) | Current backoff handles HTTP 429 rate limits; retry logic needs extension to handle transient 5xx provider overload errors | Open |

---

## 5. Key Decisions and Trade-offs

### 1. Architecture Style: Modular Monolith vs. Microservices
- **Options Considered:** Microservices vs. Modular Monolith.
- **Decision:** Modular Monolith using Clean Architecture layering (API → Services → Repositories → Domain).
- **Why:** The 2-person team needed rapid delivery without the operational overhead of service meshes, Kubernetes, distributed transactions, or network latency between components.
- **Trade-off Accepted:** Boundaries are enforced by software architecture conventions and linting rather than hard physical network barriers.
- **Reversal Trigger:** If independent teams require decoupled release cadences, or if quant worker resource requirements demand distinct runtime platforms (e.g. C++/Rust).

### 2. Evaluation Method: Deterministic Scorer vs. LLM-as-a-Judge
- **Options Considered:** LLM-as-a-judge (prompting a frontier model to score answers) vs. Deterministic programmatic evaluation.
- **Decision:** Deterministic `EvalService` measuring Retrieval Hit@5, Citation Accuracy (regex), Canonical Format Compliance, and Numeric Answer Matching (with 5% relative tolerance).
- **Why:** LLM judges introduce latency, API cost, non-deterministic drift, and judge biases. Deterministic evaluation is 100% reproducible, zero-cost per run, and unit-testable (`tests/test_eval.py`).
- **Trade-off Accepted:** Requires pre-curated ground truth questions and answers over a controlled benchmark corpus; cannot grade qualitative prose style.
- **Reversal Trigger:** If evaluating subjective, open-ended research summaries where answers have no fixed factual or numerical ground truth.

### 3. Quantitative Calculations: Deterministic Tools vs. LLM Direct Math
- **Options Considered:** Allowing the LLM to compute indicators/returns in prompt vs. Tool-calling into pure Python domain code.
- **Decision:** The LLM is strictly prohibited from doing arithmetic; all quantitative values are generated by deterministic domain services (`pandas`, `numpy`, `backtesting.py`).
- **Why:** LLMs hallucinate calculations and lack institutional numerical rigor (e.g., Wilder smoothing, sample standard deviations, leap-year CAGR).
- **Trade-off Accepted:** Added tool-calling roundtrips, schema validation overhead, and potential agent tool execution failures.
- **Reversal Trigger:** Never for quantitative financial data.

### 4. Backtest Execution: Async Celery Task with 202 and Idempotent Claim
- **Options Considered:** Synchronous HTTP request vs. FastAPI background task vs. Celery task returning `202 Accepted` with atomic CAS claim.
- **Decision:** Celery task with atomic database compare-and-swap (`UPDATE ... WHERE status='QUEUED'`) and `Idempotency-Key` deduplication.
- **Why:** Backtests can take seconds or minutes; synchronous execution risks HTTP connection timeouts and worker thread exhaustion. The atomic CAS claim guarantees single execution under Celery's at-least-once delivery.
- **Trade-off Accepted:** Clients must poll for completion; requires Redis broker infrastructure.
- **Reversal Trigger:** If backtest calculations become sub-10ms vectorized in-memory queries where broker dispatch latency dominates.

### 5. Redis Failure Mode: Fail-Open vs. Fail-Closed
- **Options Considered:** Fail-closed (reject requests if Redis is unreachable) vs. Fail-open (bypass cache and rate limiting).
- **Decision:** Fail-open for both rate limiting and query embedding cache.
- **Why:** Rate limiting and embedding caches are operational cost guards, not security authorization boundaries. A Redis glitch should not trigger an outage for user research workflows. Redis health is separately exposed via `GET /ready`.
- **Trade-off Accepted:** Temporary loss of rate limiting protection and increased LLM API spend during a Redis outage.
- **Reversal Trigger:** If rate limiting is elevated to a strict compliance, billing, or security boundary.

### 6. Secondary Model Provider: Optional NVIDIA NIM Provider
- **Options Considered:** Gemini-only vs. Full multi-provider abstraction vs. Optional NIM provider behind configuration switch.
- **Decision:** NIM added as an optional LLM provider behind a config switch (`LLM_PROVIDER=nim`). Gemini (`gemini-3.6-flash`) remains default; embeddings remain on Gemini. Nemotron 3 Ultra (`nvidia/nemotron-3-ultra-550b-a55b`) verified; GLM 5.3 Flash and Kimi K3 timed out in probes and remain unverified candidates.
- **Why:** Bypasses Gemini free-tier daily call limits (~20 calls/day) for testing and evaluation without refactoring core agent graphs (`app/ai/llm_factory.py`, `app/ai/model_registry.py`).
- **Trade-off Accepted:** Secondary API key required; embeddings still depend on Gemini due to asymmetric task-type requirements; differing model error rates under load.
- **Reversal Trigger:** If Gemini API quotas are significantly expanded or multi-model maintenance creates prompt divergence.

---

## 6. Quality Gates

1. **Continuous Integration (CI):**
   - GitHub Actions workflow ([.github/workflows/ci.yml](../.github/workflows/ci.yml)) runs on all pushes and pull requests.
   - Spins up live service containers for PostgreSQL 16 (with pgvector) and Redis 7 on Ubuntu runners (no mocking of datastores).
   - Enforces formatting (`ruff format --check .`) and static linting (`ruff check .`, rules E, F, I).
   - Enforces automated test suite execution with a hard coverage floor (`--cov-fail-under=63`).
2. **Automated Test Suite:**
   - **154 automated tests**, all passing across 16 test modules.
   - Comprehensive unit and integration coverage: authentication, indicator numerical accuracy against known-answer values, strategy AST validation, backtest idempotency, tool schema enforcement, vector search tenant isolation, and Prometheus metric generation.
   - Test isolation via `tests/conftest.py`: drops and recreates schema per test against an isolated test database (`quantpilot_test`), preserving development data.
3. **Deterministic Evaluation Harness:**
   - Evaluates RAG retrieval and generation accuracy across 15 curated financial benchmark questions against a synthetic 5-page 10-K report (`tests/fixtures/benchmark_report.pdf`).
   - Programmatically verifies 4 distinct criteria: Retrieval Hit@5 (15/15), Citation Accuracy (15/15), Canonical Format Compliance (`[Source: <filename>, Page: <n>]`), and Numeric Value Match within 5% relative tolerance.

---

## 7. Lessons Learned

1. **Decouple from External Provider Lifecycles Early:** Upstream LLM providers deprecate models and enforce aggressive rate limits unpredictably (e.g. Google's shutdown of `gemini-2.0-flash` on June 1, 2026, and its ~20 call/day free tier). Abstracting model instantiation behind an internal factory and introducing local embedding caching and secondary providers (NIM) was vital for uninterrupted engineering progress.
2. **Synchronous/Asynchronous Boundaries Require Strict Lifecycle Isolation:** Bridging async web frameworks (FastAPI/asyncpg) with synchronous task queues (Celery) caused subtle bugs (e.g., connection corruption from sharing async engines across forked processes). Creating and disposing task-local database engines per Celery run, combined with atomic CAS status claims, proved necessary for stable background execution.
3. **Subordinate Data Pipelines to Audit and Citation Requirements:** Naive document chunking (arbitrary character splits) breaks page-level citability. Constraining the chunker to sentence-greedy packing within strict page boundaries ensured that every retrieved vector corresponded to an exact page citation, directly enabling deterministic compliance verification.

---

