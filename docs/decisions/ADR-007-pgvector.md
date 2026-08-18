# ADR-007: pgvector for Vector Storage

**Status**: Accepted
**Date**: 2026-08-17
**Decision**: Use pgvector (PostgreSQL extension) for vector embedding storage and similarity search instead of a dedicated vector database.

## Context

RAG requires storing document chunk embeddings (768-dimensional vectors from gemini-embedding-2) and performing cosine similarity searches at query time.

## Decision

Use **pgvector** with HNSW indexing inside the existing PostgreSQL 16 instance.

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| Pinecone | Managed service; adds external dependency, cost, and network latency |
| Weaviate | Separate infrastructure to deploy and manage |
| Qdrant | Same as Weaviate — separate system for <100K vectors |
| FAISS | In-memory only; not persistent; no SQL integration; not suitable for production |
| ChromaDB | Additional dependency; doesn't integrate with existing PostgreSQL transactions |

## Rationale

1. **No additional infrastructure** — vectors stored in the same PostgreSQL instance used for all other data
2. **ACID transactions** — document ingestion (chunks + embeddings) is atomic
3. **Single backup/restore** — one database contains everything
4. **Sufficient scale** — a handful of 10-K PDFs produces thousands of chunks, not millions
5. **HNSW index** — provides good approximate nearest neighbor search performance

### Embedding Configuration

| Property | Value | Rationale |
|---|---|---|
| Provider | Google Gemini | Consistent with LLM provider choice |
| Model | `gemini-embedding-2` | Good quality, supported model |
| Dimension | 768 | Model default |
| Distance metric | Cosine | Standard for normalized text embeddings |
| Index type | HNSW | Better recall than IVFFlat at this scale |
| Top-K | 5 | Sufficient context for most queries |

## Consequences

### Benefits
- Zero additional infrastructure
- Transactional consistency between document metadata and vector embeddings
- Single connection pool and single point of management
- Simpler Docker Compose configuration

### Costs
- Lower performance than dedicated vector DBs at scale (>1M vectors)
- Fewer vector-specific features (no hybrid search beyond SQL WHERE clauses)
- PostgreSQL query planner not optimized for vector-heavy workloads

### Scale Threshold
If the project ever needs >1M vectors or sub-millisecond search: migration to a dedicated vector DB is feasible because the retrieval logic is isolated in `RetrievalService`. The service interface doesn't expose pgvector internals to the rest of the application.

### Interview Answer
> "I used pgvector because the vector volume for this project — a handful of financial PDFs — doesn't justify a separate vector database. PostgreSQL with pgvector handles relational data, JSON strategies, and vector embeddings in one system. If I needed to scale to millions of documents, I'd migrate the vector search to a dedicated DB without changing the service layer."
