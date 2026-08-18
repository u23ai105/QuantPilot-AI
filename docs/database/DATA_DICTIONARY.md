# QuantPilot AI — Data Dictionary

## 1. Users Domain

### `users`

| Column | Type | Nullable | Default | Domain | Description |
|---|---|---|---|---|---|
| `id` | UUID | NO | gen_random_uuid() | System-generated | Unique user identifier |
| `email` | VARCHAR(255) | NO | — | RFC 5322 email | User's login email |
| `hashed_password` | VARCHAR(255) | NO | — | bcrypt hash string | Never stored in plaintext |
| `created_at` | TIMESTAMPTZ | NO | now() | UTC timestamp | Account creation time |
| `updated_at` | TIMESTAMPTZ | NO | now() | UTC timestamp | Last profile modification |

---

## 2. Market Data Domain

### `tickers`

| Column | Type | Nullable | Default | Domain | Description |
|---|---|---|---|---|---|
| `id` | INTEGER | NO | SERIAL | Auto-increment | Internal ticker identifier |
| `symbol` | VARCHAR(10) | NO | — | Uppercase ticker (e.g., "AAPL") | Exchange ticker symbol |
| `name` | VARCHAR(255) | NO | — | Free text | Company/security name |
| `sector` | VARCHAR(100) | YES | NULL | Free text | Industry sector classification |
| `is_active` | BOOLEAN | NO | true | true/false | Whether ticker is actively tracked |

### `ohlcv`

| Column | Type | Nullable | Default | Domain | Description |
|---|---|---|---|---|---|
| `id` | BIGINT | NO | BIGSERIAL | Auto-increment | Row identifier |
| `ticker_id` | INTEGER | NO | — | FK → tickers | Which security |
| `date` | DATE | NO | — | Trading date (no time) | Date of the bar |
| `open` | NUMERIC(12,4) | NO | — | Price in USD, 4 decimal places | Opening price |
| `high` | NUMERIC(12,4) | NO | — | Price in USD, must be ≥ low | Highest price |
| `low` | NUMERIC(12,4) | NO | — | Price in USD, must be ≤ high | Lowest price |
| `close` | NUMERIC(12,4) | NO | — | Price in USD | Closing price |
| `volume` | BIGINT | NO | — | Non-negative integer | Trading volume (shares) |

---

## 3. Strategy & Backtest Domain

### `strategies`

| Column | Type | Nullable | Default | Domain | Description |
|---|---|---|---|---|---|
| `id` | INTEGER | NO | SERIAL | Auto-increment | Strategy identifier |
| `user_id` | UUID | NO | — | FK → users | Owning user |
| `name` | VARCHAR(255) | NO | — | Free text | Human-readable strategy name |
| `rules_json` | JSONB | NO | — | Validated JSON schema | Declarative strategy rules |
| `version` | INTEGER | NO | 1 | Positive integer | Schema version for forward compatibility |
| `created_at` | TIMESTAMPTZ | NO | now() | UTC timestamp | Creation time |
| `updated_at` | TIMESTAMPTZ | NO | now() | UTC timestamp | Last modification |

### `backtests`

| Column | Type | Nullable | Default | Domain | Description |
|---|---|---|---|---|---|
| `id` | INTEGER | NO | SERIAL | Auto-increment | Backtest identifier |
| `strategy_id` | INTEGER | NO | — | FK → strategies | Which strategy to test |
| `ticker_id` | INTEGER | NO | — | FK → tickers | Which security to test on |
| `start_date` | DATE | NO | — | Must be < end_date | Backtest start |
| `end_date` | DATE | NO | — | Must be > start_date | Backtest end |
| `initial_capital` | NUMERIC(14,2) | NO | 10000.00 | Positive USD amount | Starting capital |
| `commission` | NUMERIC(6,4) | NO | 0.001 | Decimal fraction 0–1 | Per-trade commission rate |
| `status` | VARCHAR(20) | NO | 'QUEUED' | Enum: QUEUED, RUNNING, COMPLETED, FAILED | Current job status |
| `celery_task_id` | VARCHAR(255) | YES | NULL | Celery task UUID | For task tracking |
| `error_message` | TEXT | YES | NULL | Free text | Error details if FAILED |
| `created_at` | TIMESTAMPTZ | NO | now() | UTC timestamp | Submission time |
| `updated_at` | TIMESTAMPTZ | NO | now() | UTC timestamp | Last status change |

### `backtest_results`

| Column | Type | Nullable | Default | Domain | Description |
|---|---|---|---|---|---|
| `id` | INTEGER | NO | SERIAL | Auto-increment | Result identifier |
| `backtest_id` | INTEGER | NO | — | FK → backtests (UNIQUE) | One result per backtest |
| `total_return` | NUMERIC(10,4) | NO | — | Decimal fraction (0.15 = 15%) | Total percentage return |
| `cagr` | NUMERIC(10,4) | NO | — | Decimal fraction | Compound annual growth rate |
| `volatility` | NUMERIC(10,4) | NO | — | Decimal fraction, annualized | Standard deviation of returns |
| `sharpe_ratio` | NUMERIC(10,4) | NO | — | Ratio (can be negative) | Risk-adjusted return |
| `sortino_ratio` | NUMERIC(10,4) | NO | — | Ratio (can be negative) | Downside risk-adjusted return |
| `max_drawdown` | NUMERIC(10,4) | NO | — | Decimal fraction (0.20 = 20%) | Maximum peak-to-trough decline |
| `win_rate` | NUMERIC(6,4) | NO | — | Decimal fraction 0–1 | Fraction of winning trades |
| `total_trades` | INTEGER | NO | — | Non-negative integer | Total number of trades |
| `equity_curve_json` | JSONB | NO | — | Array of {date, value} | Equity curve over time |
| `trades_json` | JSONB | NO | — | Array of trade records | Individual trade details |
| `created_at` | TIMESTAMPTZ | NO | now() | UTC timestamp | When results were computed |

---

## 4. Document / RAG Domain

### `documents`

| Column | Type | Nullable | Default | Domain | Description |
|---|---|---|---|---|---|
| `id` | INTEGER | NO | SERIAL | Auto-increment | Document identifier |
| `user_id` | UUID | NO | — | FK → users | Uploading user |
| `filename` | VARCHAR(255) | NO | — | Original user filename | For display only, not used in storage |
| `storage_path` | VARCHAR(500) | NO | — | System-generated safe path | Internal file location |
| `file_size` | INTEGER | NO | — | Positive integer (bytes) | File size for validation |
| `page_count` | INTEGER | YES | NULL | Positive integer | Set after PDF extraction |
| `status` | VARCHAR(20) | NO | 'UPLOADING' | Enum: UPLOADING, PROCESSING, COMPLETED, FAILED | Ingestion status |
| `error_message` | TEXT | YES | NULL | Free text | Error details if FAILED |
| `uploaded_at` | TIMESTAMPTZ | NO | now() | UTC timestamp | Upload time |
| `processed_at` | TIMESTAMPTZ | YES | NULL | UTC timestamp | Processing completion time |

### `document_chunks`

| Column | Type | Nullable | Default | Domain | Description |
|---|---|---|---|---|---|
| `id` | INTEGER | NO | SERIAL | Auto-increment | Chunk identifier |
| `document_id` | INTEGER | NO | — | FK → documents | Parent document |
| `page_number` | INTEGER | NO | — | 1-indexed, ≥ 1 | PDF page this chunk came from |
| `chunk_index` | INTEGER | NO | — | 0-indexed, ≥ 0 | Order within the page |
| `chunk_text` | TEXT | NO | — | Extracted text (~500 tokens) | Raw text content |
| `embedding` | vector(768) | NO | — | 768-dim float vector | gemini-embedding-2 output |

---

## 5. Conversation Domain

### `conversations`

| Column | Type | Nullable | Default | Domain | Description |
|---|---|---|---|---|---|
| `id` | UUID | NO | gen_random_uuid() | System-generated | Conversation identifier |
| `user_id` | UUID | NO | — | FK → users | Owning user |
| `title` | VARCHAR(255) | YES | NULL | Free text | Optional conversation title |
| `created_at` | TIMESTAMPTZ | NO | now() | UTC timestamp | Conversation start |
| `updated_at` | TIMESTAMPTZ | NO | now() | UTC timestamp | Last message time |

### `messages`

| Column | Type | Nullable | Default | Domain | Description |
|---|---|---|---|---|---|
| `id` | INTEGER | NO | SERIAL | Auto-increment | Message identifier |
| `conversation_id` | UUID | NO | — | FK → conversations | Parent conversation |
| `role` | VARCHAR(20) | NO | — | Enum: USER, ASSISTANT, TOOL | Message sender role |
| `content` | TEXT | NO | — | Free text | Message text content |
| `tool_calls_json` | JSONB | YES | NULL | Array of tool call objects | LLM's requested tool calls |
| `tool_results_json` | JSONB | YES | NULL | Array of tool result objects | Results from tool execution |
| `citations_json` | JSONB | YES | NULL | Array of {document_id, page_number} | Document citations in response |
| `created_at` | TIMESTAMPTZ | NO | now() | UTC timestamp | Message timestamp |

---

## 6. Evaluation Domain

### `eval_questions`

| Column | Type | Nullable | Default | Domain | Description |
|---|---|---|---|---|---|
| `id` | INTEGER | NO | SERIAL | Auto-increment | Question identifier |
| `question` | TEXT | NO | — | Free text | Evaluation question |
| `expected_answer` | TEXT | NO | — | Free text | Known correct answer |
| `expected_document_id` | INTEGER | YES | NULL | FK → documents | Document containing the answer |
| `expected_page` | INTEGER | YES | NULL | 1-indexed, ≥ 1 | Page containing the answer |
| `created_at` | TIMESTAMPTZ | NO | now() | UTC timestamp | Question creation time |

### `eval_runs`

| Column | Type | Nullable | Default | Domain | Description |
|---|---|---|---|---|---|
| `id` | INTEGER | NO | SERIAL | Auto-increment | Run identifier |
| `question_id` | INTEGER | NO | — | FK → eval_questions | Which question was evaluated |
| `run_at` | TIMESTAMPTZ | NO | now() | UTC timestamp | Evaluation timestamp |
| `retrieved_chunks_json` | JSONB | YES | NULL | Array of chunk summaries | Top-K chunks that were retrieved |
| `retrieval_hit_at_k` | BOOLEAN | NO | — | true/false | Was expected page in top-K results? |
| `citation_correct` | BOOLEAN | NO | — | true/false | Did the answer cite the expected page? |
| `answer_score` | NUMERIC(4,2) | NO | — | 0.00 – 1.00 | Heuristic answer quality score |
| `actual_answer` | TEXT | NO | — | Free text | Agent's actual response |
| `actual_citations_json` | JSONB | YES | NULL | Array of {document_id, page_number} | Citations in agent's response |
