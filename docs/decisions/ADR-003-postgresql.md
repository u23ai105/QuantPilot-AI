# ADR-003: PostgreSQL as Primary Database

**Status**: Accepted
**Date**: 2026-08-17
**Decision**: Use PostgreSQL as the single database for relational data and vector storage.

## Context

QuantPilot needs to store relational data (users, strategies, backtests), time-series data (OHLCV), and vector embeddings (document chunks for RAG).

## Decision

Use **PostgreSQL 16** with the **pgvector** extension for all storage needs.

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| MySQL | Less capable JSONB support, no native vector extension |
| MongoDB | Unnecessary for this schema; relational integrity needed for FK relationships |
| TimescaleDB | OHLCV data volume doesn't justify a time-series extension |
| Separate vector DB (Pinecone, Weaviate) | Adds infrastructure complexity for <100K vectors |

## Consequences

### Benefits
- **Single database** — simpler operations, single backup, single connection pool
- **ACID transactions** — critical for backtest result consistency
- **pgvector** — native vector similarity search without additional infrastructure
- **JSONB** — native JSON support for strategy rules and trade data
- **Mature ecosystem** — excellent Python support (SQLAlchemy, asyncpg, Alembic)
- **Interview answer**: "I chose PostgreSQL because it handles relational data, JSON strategies, and vector embeddings in one system, avoiding the operational complexity of multiple databases for a project at this scale."

### Costs
- pgvector has lower performance than dedicated vector DBs at scale (>1M vectors)
- Single database is a single point of failure

### Scale Threshold
If vector search volume exceeds ~100K chunks or query latency becomes unacceptable, consider migrating to a dedicated vector DB. This is unlikely for the project's scope (handful of 10-K PDFs).
