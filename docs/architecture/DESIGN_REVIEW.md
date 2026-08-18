# QuantPilot AI — Design Review

## 1. Architecture Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **LangGraph API changes** | Medium | Pin version in requirements; adapter pattern isolates LLM layer |
| **Gemini rate limits** | Medium | Free tier has 15 RPM; implement retry with backoff; batch embeddings |
| **yfinance API instability** | Low | Cache all data in PostgreSQL; never depend on live yfinance for user-facing requests |
| **MemorySaver data loss** | Low | Conversation history also persisted in PostgreSQL; MemorySaver is supplementary |
| **pgvector performance at scale** | Low | Current scale (<100K vectors) is well within pgvector capability |
| **backtesting.py limitations** | Low | Sufficient for single-ticker declarative strategies; not a backtest engine showcase |

## 2. Open Assumptions

| Assumption | Impact if Wrong | Fallback |
|---|---|---|
| Gemini 3.6 Flash has reliable tool-calling | Agent may fail to call tools correctly | Switch to gemini-1.5-pro or adjust prompts |
| gemini-embedding-2 produces 768d vectors | pgvector column dimension mismatch | Update `vector(768)` in schema |
| 10-K PDFs have extractable text (not scanned images) | PyMuPDF returns empty pages | Document status=FAILED with clear error |
| ~500 token chunks provide sufficient retrieval granularity | Low retrieval quality | Adjust chunk size; add overlap |
| Risk-free rate = 0 for Sharpe calculation | Sharpe values slightly inflated | Document assumption; make configurable |
| 252 trading days per year | Minor metric differences | Document assumption; standard convention |

## 3. Deliberate Simplifications

| Simplification | Rationale |
|---|---|
| **Single LLM provider** (no multi-provider abstraction) | Locked scope. One adapter is enough. Multi-provider adds complexity without learning value. |
| **MemorySaver** (in-memory checkpointing) | Simpler than PostgreSQL-backed persistence. Conversation history is also in the messages table. |
| **No chunk overlap** | Page boundary rule already ensures context continuity. Overlap adds complexity. |
| **No similarity threshold** | Return top-K regardless. Let the LLM judge relevance. Avoids false negatives. |
| **Asynchronous document ingestion** | Mandatory per scope. Requires Celery task `embed_document`. |
| **No idempotency keys for backtests** | Duplicate submissions are harmless. Each creates a separate record. |
| **No refresh tokens** | Access tokens only. 30-minute expiry. Sufficient for demo. |
| **Fixed ticker universe** (~30–50 symbols) | Avoids arbitrary data ingestion. Keeps scope bounded. |
| **Single worker process** | Sufficient for development. Scalable via Docker Compose replicas. |

## 4. Known Limitations

| Limitation | Impact | When It Matters |
|---|---|---|
| No real-time market data | Stale prices | Only matters for live trading (out of scope) |
| No portfolio-level analysis | Can't analyze multi-asset strategies | Out of scope by design |
| No multi-ticker backtests | Single-symbol backtests only | Out of scope by design |
| No OCR for scanned PDFs | Scanned documents produce empty text | Users must upload text-based PDFs |
| No conversation forking | Each conversation is linear | Acceptable for demo |
| No user management (admin) | No way to manage users except via DB | Acceptable for single-user demo |
| Equity curve as JSON | Large JSONB field for long backtests | Acceptable at this scale |

## 5. Future Scaling Path (Hypothetical)

| Bottleneck | Solution | Trigger |
|---|---|---|
| API throughput | Multiple uvicorn workers + gunicorn | >100 concurrent users |
| Backtest queue depth | Multiple Celery workers | >50 concurrent backtests |
| Database read load | PostgreSQL read replicas | High read traffic |
| Vector search latency | Dedicated vector DB (Qdrant/Pinecone) | >1M chunks |
| LLM rate limits | Paid tier or caching | >15 RPM sustained |
| Module coupling | Extract to separate services | >3 developers |

**None of these are built.** They exist for interview discussion only.

## 6. Things We Intentionally Did Not Build

| Feature | Reason |
|---|---|
| **Kafka** | No event-driven architecture needed. Direct function calls suffice in a monolith. |
| **Kubernetes** | Single Docker Compose is appropriate for development and demo. |
| **Microservices** | One developer, one codebase. Microservices add overhead without benefit. |
| **VectorBT** | backtesting.py is simpler and the project's differentiation is in AI, not backtest engine. |
| **Multi-LLM abstraction** | One provider is sufficient. Building an abstraction layer is scope creep. |
| **Custom vector database** | pgvector inside PostgreSQL handles the scale. |
| **Live/paper trading** | Execution is out of scope. This is a research assistant. |
| **Portfolio optimization** | Mean-variance, efficient frontier, etc. — real math, but teaches neither SDE nor GenAI. |
| **Visual strategy builder** | One declarative JSON format is sufficient. |
| **News ingestion** | Data engineering effort with poor ROI for this project's goals. |
| **Screener / Watchlists** | Trivial CRUD. No learning value. |
| **Large frontend** | Backend and AI are the focus. A 3-screen demo is sufficient. |
| **Google/GitHub OAuth** | JWT with email/password demonstrates auth concepts adequately. |
| **2FA** | Authentication complexity beyond scope. |
| **Prometheus/Grafana** | Structured logging + health endpoints are sufficient for observability. |

## 7. Design Consistency Verification

### Requirement Traceability

| AGENTS.md Requirement | Module | Database | API | Service | Test |
|---|---|---|---|---|---|
| JWT authentication | Auth | `users` | `/auth/*` | `AuthService` | `test_auth.py` |
| Password hashing | Auth | `users.hashed_password` | — | `AuthService` | `test_auth.py` |
| OHLCV storage | Market Data | `tickers`, `ohlcv` | `/market-data/*` | `MarketDataService` | `test_market_data.py` |
| SMA/EMA/RSI/MACD/BB/ATR | Quant | (computed) | `/indicators/*` | `IndicatorService` | `test_indicators.py` |
| Declarative JSON strategy | Strategies | `strategies` | `/strategies/*` | `StrategyService` | `test_strategy_*.py` |
| Async backtesting (Celery) | Backtesting | `backtests`, `backtest_results` | `/backtests/*` | `BacktestService` | `test_backtests.py` |
| Performance metrics | Backtesting | `backtest_results` | `/backtests/{id}/results` | `MetricsCalculator` | `test_metrics.py` |
| LangGraph agent | AI Agent | — | `/conversations/*/messages` | `AgentService` | `test_tools.py` |
| 5 tools (deterministic) | AI Agent | — | — | Tool → Service delegation | `test_tools.py` |
| Streaming responses | AI Agent | — | SSE | `AgentService` | — |
| PDF ingestion (PyMuPDF) | RAG | `documents`, `document_chunks` | `/documents` | `DocumentService` | `test_documents.py` |
| pgvector retrieval | RAG | `document_chunks.embedding` | — | `RetrievalService` | `test_retrieval.py` |
| Page-level citations | RAG | `document_chunks.page_number` | `citations_json` | — | `test_retrieval.py` |
| Evaluation harness | Evaluation | `eval_questions`, `eval_runs` | `/evaluation/*` | `EvaluationService` | `test_eval_harness.py` |
| Docker Compose | Deployment | — | — | — | `docker-compose.yml` |
| GitHub Actions CI | Deployment | — | — | — | `.github/workflows/ci.yml` |
| Structured logging | Cross-cutting | — | — | — | — |

### Confirmed

- ✅ Modular monolith
- ✅ Clean/hexagonal layering
- ✅ PostgreSQL
- ✅ pgvector
- ✅ Redis + Celery
- ✅ backtesting.py
- ✅ LangGraph
- ✅ Gemini 3.6 Flash
- ✅ gemini-embedding-2
- ✅ 768-dimensional embeddings
- ✅ 5 agent tools
- ✅ 1 document type
- ✅ 1 strategy format

### Explicitly out of scope

- ❌ Kafka
- ❌ Kubernetes
- ❌ microservices
- ❌ VectorBT
- ❌ multi-LLM architecture
- ❌ custom vector database
- ❌ paper/live trading
- ❌ portfolio optimization
- ❌ screener
- ❌ watchlists
- ❌ large frontend

### Async tasks

- ⚙️ backtest
- ⚙️ embedding

---

## 8. Implementation Roadmap

### Phase 0: Repository Scaffold (2–3 days)

**Objective**: Bootable empty application in Docker

**Work**:
- Initialize Python project with pyproject.toml
- Create package structure (`app/` with all subdirectories)
- Create Dockerfile and docker-compose.yml
- Create `.env.example`
- Create Alembic configuration
- Create `app/main.py` with FastAPI app
- Create `app/config.py` with Pydantic Settings
- Create health endpoints
- Setup Ruff configuration
- Setup initial GitHub Actions CI (lint only)
- Update README.md

**Definition of Done**: `docker compose up` boots FastAPI; `/health` returns 200; CI runs ruff.

---

### Phase 1: SDE Foundation (1–2 weeks)

**Objective**: Authentication, database, CI, first tests

**Work**:
- Create SQLAlchemy models (users table)
- Create initial Alembic migration
- Implement `UserRepository`
- Implement `AuthService` (register, login, JWT)
- Create auth routes (`/auth/register`, `/auth/login`)
- Create `get_current_user` dependency
- Create error handling middleware
- Create request ID middleware
- Setup structured logging (structlog)
- Write auth integration tests
- Add pytest to CI

**Prerequisites**: Phase 0 complete

**Definition of Done**: Can register/login a user; protected endpoints reject unauthenticated requests; CI runs ruff + pytest green.

---

### Phase 2: Market Data + Indicators (1 week)

**Objective**: OHLCV ingestion and indicator calculations with known-answer tests

**Work**:
- Create SQLAlchemy models (tickers, ohlcv)
- Create Alembic migration
- Implement `YFinanceAdapter`
- Implement `MarketDataRepository` (with upsert)
- Implement `MarketDataService`
- Implement all 6 indicator calculators (domain/)
- Implement `IndicatorService`
- Create market data and indicator routes
- Create ticker seeding script
- Write unit tests for all indicators (known-answer)
- Write integration tests for market data

**Prerequisites**: Phase 1 complete

**Definition of Done**: Indicators match hand-computed values on known series; OHLCV data fetched and stored correctly.

---

### Phase 3: Strategies + Backtesting (1.5–2 weeks)

**Objective**: Async backtest execution with Celery

**Work**:
- Create SQLAlchemy models (strategies, backtests, backtest_results)
- Create Alembic migration
- Implement `StrategyValidator`
- Implement `StrategyInterpreter` (JSON → backtesting.py)
- Implement `StrategyService` and `StrategyRepository`
- Implement `MetricsCalculator` (all 7 metrics)
- Setup Celery + Redis
- Implement `run_backtest` Celery task
- Implement `BacktestService` and `BacktestRepository`
- Create strategy and backtest routes
- Write unit tests for metrics (known-answer)
- Write unit tests for strategy validation
- Write integration tests for backtest submission

**Prerequisites**: Phase 2 complete (need OHLCV data)

**Definition of Done**: A hand-computable strategy's Sharpe matches backtest output; backtests run asynchronously via Celery.

---

### Phase 4: AI Agent (1.5–2 weeks)

**Objective**: LangGraph agent with 4 calculation tools + streaming

**Work**:
- Setup LangGraph with StateGraph
- Implement `GeminiLLMAdapter`
- Implement tool adapters: `get_market_data`, `calculate_indicators`, `run_backtest`, `get_performance_metrics`
- Implement `AgentService`
- Create conversation and message routes
- Implement SSE streaming
- Create `ConversationService` and `ConversationRepository`
- Implement tool error handling
- Write deterministic tool tests

**Prerequisites**: Phase 3 complete (need all services for tools)

**Definition of Done**: Agent answers "what's the Sharpe of X" by calling tools, never inventing the number; streaming works.

---

### Phase 5: RAG (1.5–2 weeks)

**Objective**: Document upload → RAG → citations

**Work**:
- Create SQLAlchemy models (documents, document_chunks with pgvector)
- Create Alembic migration (with pgvector extension)
- Implement `PDFExtractor` (PyMuPDF)
- Implement `TextChunker`
- Implement `GeminiEmbeddingAdapter`
- Implement `DocumentService` (ingestion pipeline)
- Implement `RetrievalService` (cosine similarity search)
- Implement `search_documents` tool
- Create document routes
- Wire citations through agent → response → API
- Write integration tests for retrieval

**Prerequisites**: Phase 4 complete (need agent for tool integration)

**Definition of Done**: Agent answers a 10-K question with a correct page citation; citation metadata preserved end-to-end.

---

### Phase 6: Evaluation Harness (3–5 days)

**Objective**: Measurable RAG quality

**Work**:
- Create SQLAlchemy models (eval_questions, eval_runs)
- Create Alembic migration
- Create 15–20 evaluation Q/A pairs
- Implement `RetrievalScorer`, `CitationScorer`, `AnswerScorer`
- Implement `EvaluationService`
- Implement `EvaluationRepository`
- Create evaluation routes
- Create eval question seeding script
- Run evaluation and record results

**Prerequisites**: Phase 5 complete (need working RAG)

**Definition of Done**: Script prints hit-rate and citation accuracy across evaluation set; results persisted in database.

---

### Phase 7: Polish (1 week)

**Objective**: Production-ready quality

**Work**:
- Review and improve error handling edge cases
- Review and improve logging
- Add OpenAPI examples and tags
- Verify all tests pass
- Review security (no leaked secrets, proper validation)
- Update README with architecture diagram, setup instructions, demo instructions
- Create demo script or documentation
- Optional: thin demo UI (3 screens)

**Prerequisites**: Phase 6 complete

**Definition of Done**: Repo understandable to a stranger in 10 minutes; full demo workflow works end-to-end.

---

## 9. Recommended First Implementation Task

After this design is approved:

**Start with Phase 0 — Repository Scaffold.**

Specific first task:
1. Initialize Python project structure
2. Create `docker-compose.yml` with api, worker, db, redis
3. Create `app/main.py` with FastAPI
4. Create health endpoints
5. Verify `docker compose up` boots successfully
6. Setup Ruff and initial CI

This is the smallest verifiable increment that establishes the project foundation.

---

## 10. Final Approval Status

- **HLD internally consistent:** Yes
- **LLD internally consistent:** Yes
- **Database and API contracts align:** Yes
- **AI/RAG architecture aligns:** Yes
- **Async architecture aligns:** Yes (all required tasks moved to Celery)
- **Scope is locked:** Yes (confirmed within AGENTS.md bounds)

**Status:** ALL CORRECTIONS APPLIED. READY FOR PHASE 0 IMPLEMENTATION APPROVAL.
