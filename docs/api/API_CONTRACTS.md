# QuantPilot AI — API Contracts

**Base URL**: `/api/v1`

**Authentication**: JWT Bearer token required on all endpoints except `POST /auth/register` and `POST /auth/login`.

**Common headers**:
- `Authorization: Bearer <token>` (protected endpoints)
- `Content-Type: application/json` (request body)
- `X-Request-ID: <uuid>` (optional, for tracing)

---

## 1. Auth Endpoints

### POST `/auth/register`

**Auth**: None

**Request**:
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

| Field | Type | Validation |
|---|---|---|
| `email` | string | Valid email format (Pydantic EmailStr) |
| `password` | string | min 8, max 128 characters |

**Response 201**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "created_at": "2026-08-17T22:00:00Z"
}
```

**Errors**:
| Status | Error | When |
|---|---|---|
| 422 | `VALIDATION_ERROR` | Invalid email or password too short |
| 409 | `CONFLICT` | Email already registered |

---

### POST `/auth/login`

**Auth**: None

**Request**:
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response 200**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Errors**:
| Status | Error | When |
|---|---|---|
| 401 | `AUTHENTICATION_ERROR` | Invalid email or password |

---

## 2. Market Data Endpoints

### GET `/market-data/{symbol}`

**Auth**: Required

**Path params**: `symbol` — ticker symbol (e.g., "AAPL")

**Query params**:

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `start` | date | No | 1 year ago | Start date (YYYY-MM-DD) |
| `end` | date | No | today | End date (YYYY-MM-DD) |

**Response 200**:
```json
{
  "symbol": "AAPL",
  "bars": [
    {
      "date": "2024-01-02",
      "open": 187.15,
      "high": 188.44,
      "low": 183.89,
      "close": 185.64,
      "volume": 82488700
    }
  ],
  "count": 252
}
```

**Errors**:
| Status | Error | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Symbol not in universe, invalid date range |
| 502 | `DATA_PROVIDER_ERROR` | yfinance failure (if data not cached) |

---

## 3. Indicator Endpoints

### GET `/indicators/{symbol}`

**Auth**: Required

**Path params**: `symbol` — ticker symbol

**Query params**:

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `indicator` | string | Yes | — | One of: sma, ema, rsi, macd, bollinger, atr |
| `period` | int | No | Varies | Main period parameter |
| `fast` | int | No | 12 | MACD fast period |
| `slow` | int | No | 26 | MACD slow period |
| `signal` | int | No | 9 | MACD signal period |
| `std_dev` | float | No | 2.0 | Bollinger std deviation |
| `start` | date | No | 1 year ago | Data start date |
| `end` | date | No | today | Data end date |

**Response 200** (single-value indicator):
```json
{
  "symbol": "AAPL",
  "indicator": "rsi",
  "params": {"period": 14},
  "data": [
    {"date": "2024-01-15", "value": 62.3},
    {"date": "2024-01-16", "value": 58.7}
  ]
}
```

**Response 200** (multi-value indicator — MACD):
```json
{
  "symbol": "AAPL",
  "indicator": "macd",
  "params": {"fast": 12, "slow": 26, "signal": 9},
  "data": [
    {
      "date": "2024-01-15",
      "values": {"macd": 2.34, "signal": 1.89, "histogram": 0.45}
    }
  ]
}
```

**Errors**:
| Status | Error | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Invalid indicator, insufficient data |
| 502 | `DATA_PROVIDER_ERROR` | yfinance failure |

---

## 4. Strategy Endpoints

### POST `/strategies`

**Auth**: Required

**Request**:
```json
{
  "name": "SMA Crossover 10/30",
  "rules_json": {
    "version": 1,
    "entry": {
      "conditions": [
        {
          "indicator": "sma",
          "params": {"period": 10},
          "operator": "crosses_above",
          "against": {"indicator": "sma", "params": {"period": 30}}
        }
      ],
      "logic": "AND"
    },
    "exit": {
      "conditions": [
        {
          "indicator": "sma",
          "params": {"period": 10},
          "operator": "crosses_below",
          "against": {"indicator": "sma", "params": {"period": 30}}
        }
      ],
      "logic": "AND"
    },
    "position_sizing": {"type": "fixed_fraction", "value": 1.0}
  }
}
```

**Response 201**:
```json
{
  "id": 1,
  "name": "SMA Crossover 10/30",
  "version": 1,
  "created_at": "2026-08-17T22:00:00Z"
}
```

**Errors**:
| Status | Error | When |
|---|---|---|
| 422 | `VALIDATION_ERROR` | Invalid strategy JSON schema |
| 409 | `CONFLICT` | User already has strategy with this name |

---

### GET `/strategies`

**Auth**: Required

**Response 200**:
```json
[
  {
    "id": 1,
    "name": "SMA Crossover 10/30",
    "version": 1,
    "created_at": "2026-08-17T22:00:00Z"
  }
]
```

---

### GET `/strategies/{id}`

**Auth**: Required

**Response 200**:
```json
{
  "id": 1,
  "name": "SMA Crossover 10/30",
  "rules_json": { ... },
  "version": 1,
  "created_at": "2026-08-17T22:00:00Z",
  "updated_at": "2026-08-17T22:00:00Z"
}
```

**Errors**:
| Status | Error | When |
|---|---|---|
| 403 | `AUTHORIZATION_ERROR` | Not user's strategy |
| 404 | `NOT_FOUND` | Strategy doesn't exist |

---

## 5. Backtest Endpoints

### POST `/backtests`

**Auth**: Required

**Request**:
```json
{
  "strategy_id": 1,
  "symbol": "AAPL",
  "start_date": "2023-01-01",
  "end_date": "2024-01-01",
  "initial_capital": 10000.00,
  "commission": 0.001,
  "slippage": 0.000
}
```

| Field | Type | Required | Default | Validation |
|---|---|---|---|---|
| `strategy_id` | int | Yes | — | Must exist, must belong to user |
| `symbol` | string | Yes | — | Must be in ticker universe |
| `start_date` | date | Yes | — | Must be < end_date |
| `end_date` | date | Yes | — | Must be > start_date |
| `initial_capital` | float | No | 10000.0 | Must be > 0 |
| `commission` | float | No | 0.001 | Must be ≥ 0 |
| `slippage` | float | No | 0.000 | Must be ≥ 0 |

**Response 202**:
```json
{
  "id": 42,
  "strategy_id": 1,
  "symbol": "AAPL",
  "start_date": "2023-01-01",
  "end_date": "2024-01-01",
  "status": "QUEUED",
  "created_at": "2026-08-17T22:00:00Z"
}
```

**Errors**:
| Status | Error | When |
|---|---|---|
| 403 | `AUTHORIZATION_ERROR` | Strategy not owned by user |
| 404 | `NOT_FOUND` | Strategy or symbol not found |
| 422 | `VALIDATION_ERROR` | Invalid dates or capital |

---

### GET `/backtests/{id}`

**Auth**: Required

**Response 200**:
```json
{
  "id": 42,
  "strategy_id": 1,
  "symbol": "AAPL",
  "start_date": "2023-01-01",
  "end_date": "2024-01-01",
  "status": "COMPLETED",
  "created_at": "2026-08-17T22:00:00Z",
  "updated_at": "2026-08-17T22:05:00Z"
}
```

---

### GET `/backtests/{id}/results`

**Auth**: Required

**Response 200** (when status=COMPLETED):
```json
{
  "backtest_id": 42,
  "total_return": 0.152,
  "cagr": 0.152,
  "volatility": 0.187,
  "sharpe_ratio": 1.34,
  "sortino_ratio": 1.87,
  "max_drawdown": 0.087,
  "win_rate": 0.58,
  "total_trades": 12,
  "equity_curve": [
    {"date": "2023-01-02", "value": 10000.0},
    {"date": "2023-01-03", "value": 10150.0}
  ],
  "trades": [
    {
      "entry_date": "2023-02-15",
      "exit_date": "2023-04-10",
      "entry_price": 152.30,
      "exit_price": 164.80,
      "pnl": 1250.00,
      "return_pct": 0.082
    }
  ]
}
```

**Errors**:
| Status | Error | When |
|---|---|---|
| 404 | `NOT_FOUND` | Backtest not found or not yet completed |

---

## 6. Document Endpoints

### POST `/documents`

**Auth**: Required

**Content-Type**: `multipart/form-data`

**Request**: File upload (`file` field)

| Validation | Rule |
|---|---|
| File type | application/pdf (MIME + magic bytes) |
| File size | ≤ 50 MB |

**Response 202 Accepted**:
```json
{
  "id": 1,
  "filename": "Apple_10K_2023.pdf",
  "page_count": null,
  "status": "PROCESSING",
  "uploaded_at": "2026-08-17T22:00:00Z"
}
```

**Errors**:
| Status | Error | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Not a PDF, exceeds size limit |
| 500 | `DOCUMENT_PROCESSING_ERROR` | Extraction or embedding failure |

---

### GET `/documents`

**Auth**: Required

**Response 200**:
```json
[
  {
    "id": 1,
    "filename": "Apple_10K_2023.pdf",
    "page_count": 147,
    "status": "READY",
    "uploaded_at": "2026-08-17T22:00:00Z"
  }
]
```

---

## 7. Conversation / AI Endpoints

### POST `/conversations`

**Auth**: Required

**Request**:
```json
{
  "title": "AAPL Analysis"
}
```

**Response 201**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "AAPL Analysis",
  "created_at": "2026-08-17T22:00:00Z"
}
```

---

### POST `/conversations/{id}/messages`

**Auth**: Required

**Request**:
```json
{
  "content": "What was Apple's revenue in 2023?"
}
```

**Response**: SSE stream (Server-Sent Events)

```text
event: tool_start
data: {"tool": "search_documents", "args": {"query": "Apple revenue 2023"}}

event: tool_end
data: {"tool": "search_documents", "result_summary": "Found 3 relevant chunks"}

event: token
data: {"content": "According to "}

event: token
data: {"content": "Apple's 10-K filing"}

event: token
data: {"content": " (Page 47), ..."}

event: citations
data: {"citations": [{"document_id": 1, "page_number": 47}]}

event: done
data: {"message_id": 15}
```

**Errors**:
| Status | Error | When |
|---|---|---|
| 404 | `NOT_FOUND` | Conversation not found |
| 403 | `AUTHORIZATION_ERROR` | Not user's conversation |
| 502 | `AI_TOOL_ERROR` | LLM failure |

---

### GET `/conversations/{id}/messages`

**Auth**: Required

**Response 200**:
```json
{
  "conversation_id": "550e8400-...",
  "messages": [
    {
      "id": 1,
      "role": "USER",
      "content": "What was Apple's revenue in 2023?",
      "citations": null,
      "created_at": "2026-08-17T22:00:00Z"
    },
    {
      "id": 2,
      "role": "ASSISTANT",
      "content": "According to Apple's 10-K filing (Page 47)...",
      "citations": [{"document_id": 1, "page_number": 47}],
      "created_at": "2026-08-17T22:00:05Z"
    }
  ]
}
```

---

## 8. Evaluation Endpoints

### POST `/evaluation/run`

**Auth**: Required

**Request**: Empty body (runs all eval questions)

**Response 202**:
```json
{
  "status": "started",
  "total_questions": 20,
  "message": "Evaluation started. Use GET /evaluation/report to check results."
}
```

---

### GET `/evaluation/report`

**Auth**: Required

**Response 200**:
```json
{
  "run_at": "2026-08-17T22:30:00Z",
  "total_questions": 20,
  "retrieval_hit_rate": 0.85,
  "citation_accuracy": 0.70,
  "average_answer_score": 0.72,
  "results": [
    {
      "question_id": 1,
      "question": "What was Apple's total revenue in FY2023?",
      "retrieval_hit_at_k": true,
      "citation_correct": true,
      "answer_score": 0.90,
      "expected_page": 47,
      "actual_citations": [{"document_id": 1, "page_number": 47}]
    }
  ]
}
```

---

## 9. Health Endpoints (No Auth)

### GET `/health`

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-08-17T22:00:00Z"
}
```

### GET `/health/ready`

```json
{
  "status": "ready",
  "database": "connected",
  "redis": "connected"
}
```

---

## 10. Common Error Response Schema

All errors follow this format:

```json
{
  "error": "VALIDATION_ERROR",
  "message": "Symbol 'INVALID' is not in the supported ticker universe",
  "detail": null
}
```

| Field | Type | Description |
|---|---|---|
| `error` | string | Error category (from error hierarchy) |
| `message` | string | Human-readable error message |
| `detail` | object/null | Optional additional context (validation errors, etc.) |
