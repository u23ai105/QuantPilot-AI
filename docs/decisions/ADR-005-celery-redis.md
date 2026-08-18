# ADR-005: Celery + Redis for Async Processing

**Status**: Accepted
**Date**: 2026-08-17
**Decision**: Use Celery with Redis as both message broker and result backend for async task processing.

## Context

Backtests can take seconds to minutes. Running them inline in HTTP requests would block the API. Document embedding involves batch API calls to Gemini. Both need to run outside the request lifecycle.

## Decision

Use **Celery** for task execution with **Redis** as the message broker.

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| `asyncio.create_task()` | Tasks lost on process restart; no persistence; no monitoring |
| `background_tasks` (FastAPI) | Same process — crashes take down backtest with the request |
| `arq` (async Redis queue) | Less mature ecosystem; Celery is better documented |
| `dramatiq` | Viable alternative but Celery is more widely known |
| Kafka | Massively over-engineered for this workload; explicitly out of scope |

## Rationale

- **Celery**: Mature, well-documented, supports task routing, retry, timeout, and monitoring
- **Redis**: Lightweight, already needed for Celery broker; doubles as result backend
- **Interview answer**: "Celery gives me task persistence, retry policies, timeout handling, and worker concurrency — things I'd lose with a background thread. Redis is the lightest broker that supports reliable delivery."

## Consequences

### Benefits
- Backtests survive API process restarts
- Task status is trackable
- Built-in retry, timeout, and dead-letter handling
- Worker concurrency is configurable
- Two separate queues (backtest, embedding) allow independent scaling

### Costs
- Adds Redis + Celery worker to the Docker Compose stack
- Worker uses synchronous Python (not asyncio) — fine for CPU-bound backtests
- Task payloads must be JSON-serializable
