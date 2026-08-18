# QuantPilot AI — Deployment Architecture

## 1. Development Environment

### 1.1 Docker Compose Services

```yaml
version: "3.9"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    volumes:
      - ./app:/app/app          # Hot reload
      - uploads:/app/uploads    # Document storage
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/quantpilot
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - GEMINI_MODEL=gemini-3.6-flash

  worker:
    build:
      context: .
      dockerfile: Dockerfile
    command: >
      celery -A app.workers.celery_app worker
      --loglevel=info
      --concurrency=2
      --queues=backtest,embedding
      --prefetch-multiplier=1
    volumes:
      - uploads:/app/uploads
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/quantpilot
      - REDIS_URL=redis://redis:6379/0
      - GEMINI_API_KEY=${GEMINI_API_KEY}

  db:
    image: pgvector/pgvector:pg16
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=quantpilot
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
  uploads:
```

### 1.2 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Default command (overridden by docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 2. Service Topology

```text
┌─────────────────────────────────────────────┐
│              Docker Compose                  │
│                                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │   api   │  │ worker  │  │  redis  │     │
│  │ :8000   │  │ (celery)│  │ :6379   │     │
│  └────┬────┘  └────┬────┘  └─────────┘     │
│       │            │                         │
│       └─────┬──────┘                         │
│             │                                │
│       ┌─────▼─────┐                          │
│       │    db     │                          │
│       │  :5432   │                          │
│       │ pgvector │                          │
│       └───────────┘                          │
│                                              │
└─────────────────────────────────────────────┘
         │
    Host :8000
```

### Service Responsibilities

| Service | Image | Role | Exposed Port |
|---|---|---|---|
| `api` | Custom (Python 3.11) | FastAPI + uvicorn | 8000 (host-mapped) |
| `worker` | Custom (same image) | Celery worker | None |
| `db` | `pgvector/pgvector:pg16` | PostgreSQL + pgvector | 5432 (internal) |
| `redis` | `redis:7-alpine` | Message broker + result backend | 6379 (internal) |

---

## 3. CI/CD Pipeline

### 3.1 GitHub Actions

```text
Push / PR
    ↓
┌─────────┐
│  Lint   │  ruff check + ruff format --check
└────┬────┘
     ↓
┌─────────┐
│  Test   │  pytest (unit + integration) with PostgreSQL + Redis services
└────┬────┘
     ↓
┌─────────┐
│  Build  │  docker build (verify image builds successfully)
└─────────┘
```

### 3.2 Pipeline Details

| Stage | Tool | Trigger | Failure Behavior |
|---|---|---|---|
| Lint | Ruff | Every push/PR | Block merge |
| Test | Pytest | Every push/PR | Block merge |
| Build | Docker | Every push/PR | Block merge (verifies Dockerfile is valid) |

### 3.3 What Is NOT in CI

- Deployment to any cloud (no cloud infra)
- AI agent tests (require Gemini API key, non-deterministic)
- Evaluation harness (requires uploaded documents + API key)
- Performance/load testing

---

## 4. Observability

### 4.1 Structured Logging

```python
import structlog

logger = structlog.get_logger()

# Example log output
logger.info(
    "backtest_submitted",
    backtest_id=42,
    strategy_id=1,
    symbol="AAPL",
    user_id="abc-123",
    request_id="req-456",
)
```

**Log format**: JSON (machine-parseable)

**Log fields:**

| Field | Type | Description |
|---|---|---|
| `timestamp` | ISO 8601 | When the event occurred |
| `level` | string | INFO, WARNING, ERROR |
| `event` | string | What happened |
| `request_id` | string | Unique ID per HTTP request |
| `user_id` | string | Authenticated user (if applicable) |
| `task_id` | string | Celery task ID (if applicable) |
| `duration_ms` | int | Operation duration |
| `error` | string | Error message (if applicable) |

### 4.2 Request ID Middleware

```python
class RequestIDMiddleware:
    """Adds a unique request_id to every HTTP request for tracing."""

    async def __call__(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        # Bind to structlog context
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

### 4.3 Health Endpoints

```python
# GET /health — Application health
{"status": "healthy", "version": "0.1.0", "timestamp": "2026-08-17T22:00:00Z"}

# GET /health/ready — Readiness (checks dependencies)
{"status": "ready", "database": "connected", "redis": "connected"}
```

### 4.4 Task Logging

Celery tasks log their lifecycle:

```json
{"event": "task_started", "task_id": "abc-123", "task_name": "run_backtest", "backtest_id": 42}
{"event": "task_completed", "task_id": "abc-123", "duration_ms": 4523, "backtest_id": 42}
{"event": "task_failed", "task_id": "abc-123", "error": "Insufficient data", "backtest_id": 42}
```

---

## 5. Local Development Workflow

```text
1. Clone repository
2. Copy .env.example → .env
3. Set GEMINI_API_KEY in .env
4. docker compose up --build
5. Run migrations: docker compose exec api alembic upgrade head
6. Seed tickers: docker compose exec api python -m app.scripts.seed_tickers
7. API available at http://localhost:8000
8. OpenAPI docs at http://localhost:8000/docs
```

---

## 6. Future Scaling Path (Hypothetical — Not Built)

| Current | Future Option | When |
|---|---|---|
| Single uvicorn (dev reload) | Multiple uvicorn workers + gunicorn | > 100 concurrent users |
| Single Celery worker (concurrency=2) | Multiple workers, task routing | > 50 concurrent backtests |
| Single PostgreSQL | Read replicas | Heavy read traffic |
| pgvector HNSW in PostgreSQL | Dedicated vector DB | > 1M chunks |
| Docker Compose local | Cloud deployment (single VM) | Production demo |

**None of these are implemented.** This section exists only for interview discussion.
