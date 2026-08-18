# QuantPilot AI — Entity-Relationship Diagram

## Complete ERD

```mermaid
erDiagram
    users {
        UUID id PK
        VARCHAR email UK
        VARCHAR hashed_password
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    tickers {
        INTEGER id PK
        VARCHAR symbol UK
        VARCHAR name
        VARCHAR sector
        BOOLEAN is_active
    }

    ohlcv {
        BIGINT id PK
        INTEGER ticker_id FK
        DATE date
        NUMERIC open
        NUMERIC high
        NUMERIC low
        NUMERIC close
        BIGINT volume
    }

    strategies {
        INTEGER id PK
        UUID user_id FK
        VARCHAR name
        JSONB rules_json
        INTEGER version
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    backtests {
        INTEGER id PK
        INTEGER strategy_id FK
        INTEGER ticker_id FK
        DATE start_date
        DATE end_date
        NUMERIC initial_capital
        NUMERIC commission
        VARCHAR status
        VARCHAR celery_task_id
        TEXT error_message
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    backtest_results {
        INTEGER id PK
        INTEGER backtest_id FK "UK"
        NUMERIC total_return
        NUMERIC cagr
        NUMERIC volatility
        NUMERIC sharpe_ratio
        NUMERIC sortino_ratio
        NUMERIC max_drawdown
        NUMERIC win_rate
        INTEGER total_trades
        JSONB equity_curve_json
        JSONB trades_json
        TIMESTAMPTZ created_at
    }

    documents {
        INTEGER id PK
        UUID user_id FK
        VARCHAR filename
        VARCHAR storage_path
        INTEGER file_size
        INTEGER page_count
        VARCHAR status
        TEXT error_message
        TIMESTAMPTZ uploaded_at
        TIMESTAMPTZ processed_at
    }

    document_chunks {
        INTEGER id PK
        INTEGER document_id FK
        INTEGER page_number
        INTEGER chunk_index
        TEXT chunk_text
        vector embedding
    }

    conversations {
        UUID id PK
        UUID user_id FK
        VARCHAR title
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    messages {
        INTEGER id PK
        UUID conversation_id FK
        VARCHAR role
        TEXT content
        JSONB tool_calls_json
        JSONB tool_results_json
        JSONB citations_json
        TIMESTAMPTZ created_at
    }

    eval_questions {
        INTEGER id PK
        TEXT question
        TEXT expected_answer
        INTEGER expected_document_id FK
        INTEGER expected_page
        TIMESTAMPTZ created_at
    }

    eval_runs {
        INTEGER id PK
        INTEGER question_id FK
        TIMESTAMPTZ run_at
        JSONB retrieved_chunks_json
        BOOLEAN retrieval_hit_at_k
        BOOLEAN citation_correct
        NUMERIC answer_score
        TEXT actual_answer
        JSONB actual_citations_json
    }

    %% Relationships
    users ||--o{ strategies : "owns"
    users ||--o{ documents : "uploads"
    users ||--o{ conversations : "creates"

    tickers ||--o{ ohlcv : "has"

    strategies ||--o{ backtests : "tested by"

    tickers ||--o{ backtests : "tested on"

    backtests ||--o| backtest_results : "produces"

    documents ||--o{ document_chunks : "contains"

    conversations ||--o{ messages : "has"

    eval_questions ||--o{ eval_runs : "evaluated by"

    documents ||--o{ eval_questions : "referenced by"
```

## Relationship Summary

| Parent | Child | Cardinality | FK Column | ON DELETE |
|---|---|---|---|---|
| `users` | `strategies` | 1:N | `strategies.user_id` | CASCADE |
| `users` | `documents` | 1:N | `documents.user_id` | CASCADE |
| `users` | `conversations` | 1:N | `conversations.user_id` | CASCADE |
| `tickers` | `ohlcv` | 1:N | `ohlcv.ticker_id` | CASCADE |
| `tickers` | `backtests` | 1:N | `backtests.ticker_id` | RESTRICT |
| `strategies` | `backtests` | 1:N | `backtests.strategy_id` | CASCADE |
| `backtests` | `backtest_results` | 1:1 | `backtest_results.backtest_id` (UNIQUE) | CASCADE |
| `documents` | `document_chunks` | 1:N | `document_chunks.document_id` | CASCADE |
| `conversations` | `messages` | 1:N | `messages.conversation_id` | CASCADE |
| `eval_questions` | `eval_runs` | 1:N | `eval_runs.question_id` | CASCADE |
| `documents` | `eval_questions` | 1:N (optional) | `eval_questions.expected_document_id` | SET NULL |

## Key Uniqueness Constraints

| Table | Unique Constraint | Purpose |
|---|---|---|
| `users` | `email` | No duplicate accounts |
| `tickers` | `symbol` | No duplicate tickers |
| `ohlcv` | `(ticker_id, date)` | No duplicate daily bars |
| `strategies` | `(user_id, name)` | User can't have two strategies with same name |
| `backtest_results` | `backtest_id` | Exactly one result per backtest |
