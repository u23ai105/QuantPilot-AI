# QuantPilot AI — Database Design

## 1. Overview

- **Engine**: PostgreSQL 16
- **ORM**: SQLAlchemy (async) with asyncpg driver
- **Migrations**: Alembic
- **Vector extension**: pgvector
- **Total tables**: 12
- **Naming convention**: snake_case, plural table names

---

## 2. Table Specifications

### 2.1 `users`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK, DEFAULT gen_random_uuid() | |
| `email` | `VARCHAR(255)` | NOT NULL, UNIQUE | |
| `hashed_password` | `VARCHAR(255)` | NOT NULL | bcrypt hash |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | Updated on modification |

**Indexes:**
- `ix_users_email` — UNIQUE index on `email`

---

### 2.2 `tickers`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `INTEGER` | PK, SERIAL | |
| `symbol` | `VARCHAR(10)` | NOT NULL, UNIQUE | e.g., "AAPL" |
| `name` | `VARCHAR(255)` | NOT NULL | e.g., "Apple Inc." |
| `sector` | `VARCHAR(100)` | NULL | e.g., "Technology" |

**Indexes:**
- `ix_tickers_symbol` — UNIQUE index on `symbol`

---

### 2.3 `ohlcv`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `BIGINT` | PK, BIGSERIAL | Large dataset expected |
| `ticker_id` | `INTEGER` | NOT NULL, FK → tickers(id) ON DELETE CASCADE | |
| `date` | `DATE` | NOT NULL | Trading date |
| `open` | `NUMERIC(12,4)` | NOT NULL | |
| `high` | `NUMERIC(12,4)` | NOT NULL | |
| `low` | `NUMERIC(12,4)` | NOT NULL | |
| `close` | `NUMERIC(12,4)` | NOT NULL | |
| `volume` | `BIGINT` | NOT NULL | |

**Indexes:**
- `uq_ohlcv_ticker_date` — UNIQUE index on `(ticker_id, date)`
- `ix_ohlcv_ticker_id` — index on `ticker_id` (for FK lookups)
- `ix_ohlcv_date` — index on `date` (for range queries)

**Constraints:**
- CHECK: `high >= low`
- CHECK: `volume >= 0`

---

### 2.4 `strategies`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `INTEGER` | PK, SERIAL | |
| `user_id` | `UUID` | NOT NULL, FK → users(id) ON DELETE CASCADE | |
| `name` | `VARCHAR(255)` | NOT NULL | |
| `rules_json` | `JSONB` | NOT NULL | Declarative strategy rules |
| `version` | `INTEGER` | NOT NULL, DEFAULT 1 | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Indexes:**
- `ix_strategies_user_id` — index on `user_id`

**Constraints:**
- UNIQUE on `(user_id, name)` — user cannot have two strategies with same name

---

### 2.5 `backtests`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `INTEGER` | PK, SERIAL | |
| `strategy_id` | `INTEGER` | NOT NULL, FK → strategies(id) ON DELETE CASCADE | |
| `ticker_id` | `INTEGER` | NOT NULL, FK → tickers(id) | |
| `start_date` | `DATE` | NOT NULL | |
| `end_date` | `DATE` | NOT NULL | |
| `initial_capital` | `NUMERIC(14,2)` | NOT NULL, DEFAULT 10000.00 | |
| `commission` | `NUMERIC(6,4)` | NOT NULL, DEFAULT 0.001 | As decimal fraction |
| `slippage` | `NUMERIC(6,4)` | NOT NULL, DEFAULT 0.000 | As decimal fraction |
| `status` | `VARCHAR(20)` | NOT NULL, DEFAULT 'QUEUED' | QUEUED, RUNNING, COMPLETED, FAILED |
| `celery_task_id` | `VARCHAR(255)` | NULL | Celery task UUID |
| `error_message` | `TEXT` | NULL | Populated on FAILED |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Indexes:**
- `ix_backtests_strategy_id` — index on `strategy_id`
- `ix_backtests_status` — index on `status` (for worker queries)

**Constraints:**
- CHECK: `start_date < end_date`
- CHECK: `initial_capital > 0`
- CHECK: `commission >= 0`
- CHECK: `slippage >= 0`
- CHECK: `status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')`

---

### 2.6 `backtest_results`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `INTEGER` | PK, SERIAL | |
| `backtest_id` | `INTEGER` | NOT NULL, UNIQUE, FK → backtests(id) ON DELETE CASCADE | One result per backtest |
| `total_return` | `NUMERIC(10,4)` | NOT NULL | As decimal (0.15 = 15%) |
| `cagr` | `NUMERIC(10,4)` | NOT NULL | |
| `volatility` | `NUMERIC(10,4)` | NOT NULL | Annualized |
| `sharpe_ratio` | `NUMERIC(10,4)` | NOT NULL | |
| `sortino_ratio` | `NUMERIC(10,4)` | NOT NULL | |
| `max_drawdown` | `NUMERIC(10,4)` | NOT NULL | As decimal (0.20 = 20%) |
| `win_rate` | `NUMERIC(6,4)` | NOT NULL | As decimal (0.55 = 55%) |
| `total_trades` | `INTEGER` | NOT NULL | |
| `equity_curve_json` | `JSONB` | NOT NULL | Array of {date, value} |
| `trades_json` | `JSONB` | NOT NULL | Array of trade records |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Indexes:**
- `uq_backtest_results_backtest_id` — UNIQUE index on `backtest_id`

---

### 2.7 `documents`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `INTEGER` | PK, SERIAL | |
| `user_id` | `UUID` | NOT NULL, FK → users(id) ON DELETE CASCADE | |
| `filename` | `VARCHAR(255)` | NOT NULL | Original filename (display only) |
| `storage_path` | `VARCHAR(500)` | NOT NULL | Internal safe path |
| `file_size` | `INTEGER` | NOT NULL | Bytes |
| `page_count` | `INTEGER` | NULL | Set after extraction |
| `status` | `VARCHAR(20)` | NOT NULL, DEFAULT 'UPLOADING' | UPLOADING, PROCESSING, COMPLETED, FAILED |
| `error_message` | `TEXT` | NULL | Populated on FAILED |
| `uploaded_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `processed_at` | `TIMESTAMPTZ` | NULL | Set on completion |

**Indexes:**
- `ix_documents_user_id` — index on `user_id`

**Constraints:**
- CHECK: `status IN ('UPLOADING', 'PROCESSING', 'COMPLETED', 'FAILED')`
- CHECK: `file_size > 0`

---

### 2.8 `document_chunks`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `INTEGER` | PK, SERIAL | |
| `document_id` | `INTEGER` | NOT NULL, FK → documents(id) ON DELETE CASCADE | |
| `page_number` | `INTEGER` | NOT NULL | 1-indexed PDF page |
| `chunk_index` | `INTEGER` | NOT NULL | Sequential within page |
| `chunk_text` | `TEXT` | NOT NULL | |
| `embedding` | `vector(768)` | NOT NULL | gemini-embedding-2 output |

**Indexes:**
- `ix_document_chunks_document_id` — index on `document_id`
- `ix_document_chunks_embedding` — IVFFlat or HNSW index on `embedding` using cosine distance

**Constraints:**
- CHECK: `page_number >= 1`
- CHECK: `chunk_index >= 0`

**Embedding configuration metadata:**
```text
embedding_provider: google
embedding_model: gemini-embedding-2
embedding_dimension: 768
distance_metric: cosine
```

---

### 2.9 `conversations`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK, DEFAULT gen_random_uuid() | |
| `user_id` | `UUID` | NOT NULL, FK → users(id) ON DELETE CASCADE | |
| `title` | `VARCHAR(255)` | NULL | Optional, can be auto-generated |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Indexes:**
- `ix_conversations_user_id` — index on `user_id`

---

### 2.10 `messages`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `INTEGER` | PK, SERIAL | |
| `conversation_id` | `UUID` | NOT NULL, FK → conversations(id) ON DELETE CASCADE | |
| `role` | `VARCHAR(20)` | NOT NULL | USER, ASSISTANT, TOOL |
| `content` | `TEXT` | NOT NULL | |
| `tool_calls_json` | `JSONB` | NULL | LLM tool call requests |
| `tool_results_json` | `JSONB` | NULL | Tool execution results |
| `citations_json` | `JSONB` | NULL | [{document_id, page_number}, ...] |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Indexes:**
- `ix_messages_conversation_id` — index on `conversation_id`

**Constraints:**
- CHECK: `role IN ('USER', 'ASSISTANT', 'TOOL')`

---

### 2.11 `eval_questions`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `INTEGER` | PK, SERIAL | |
| `question` | `TEXT` | NOT NULL | |
| `expected_answer` | `TEXT` | NOT NULL | Expected answer text |
| `expected_document_id` | `INTEGER` | NULL, FK → documents(id) | NULL if not document-specific |
| `expected_page` | `INTEGER` | NULL | Expected page number |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |

**Constraints:**
- CHECK: `expected_page IS NULL OR expected_page >= 1`

---

### 2.12 `eval_runs`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `INTEGER` | PK, SERIAL | |
| `question_id` | `INTEGER` | NOT NULL, FK → eval_questions(id) ON DELETE CASCADE | |
| `run_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT now() | |
| `retrieved_chunks_json` | `JSONB` | NULL | Top-K chunks retrieved |
| `retrieval_hit_at_k` | `BOOLEAN` | NOT NULL | Was expected page in top-K? |
| `citation_correct` | `BOOLEAN` | NOT NULL | Did answer cite expected page? |
| `answer_score` | `NUMERIC(4,2)` | NOT NULL | 0.00 – 1.00 heuristic score |
| `actual_answer` | `TEXT` | NOT NULL | Agent's actual response |
| `actual_citations_json` | `JSONB` | NULL | [{document_id, page_number}, ...] |

**Indexes:**
- `ix_eval_runs_question_id` — index on `question_id`

---

## 3. pgvector Configuration

```sql
-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Column definition
embedding vector(768)

-- Index (HNSW recommended for production-quality ANN search)
CREATE INDEX ix_document_chunks_embedding
ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Design metadata:**
| Property | Value |
|---|---|
| `embedding_provider` | google |
| `embedding_model` | gemini-embedding-2 |
| `embedding_dimension` | 768 |
| `distance_metric` | cosine |
| `index_type` | HNSW |
| `top_k` | 5 (default retrieval limit) |

---

## 4. Migration Strategy

- **Tool**: Alembic with async SQLAlchemy
- **Approach**: One migration per schema change
- **Initial migration**: Creates all 12 tables + pgvector extension
- **Naming**: `{revision}_{description}.py` (e.g., `001_initial_schema.py`)
- **Environment**: Migrations run against the `db` container

---

## 5. Transaction Boundaries

| Operation | Transaction Scope |
|---|---|
| User registration | Single INSERT |
| OHLCV ingestion | Batch UPSERT within single transaction per ticker |
| Strategy creation | Single INSERT |
| Backtest submission | INSERT backtest record (status=QUEUED) |
| Backtest completion | UPDATE backtest status + INSERT backtest_results (single transaction) |
| Document ingestion | INSERT document + INSERT all chunks (single transaction; rollback on failure) |
| Message creation | INSERT message (single INSERT) |
| Eval run | INSERT eval_run (single INSERT) |
