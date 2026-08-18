# ADR-006: LangGraph for AI Agent

**Status**: Accepted
**Date**: 2026-08-17
**Decision**: Use LangGraph as the AI agent framework with Google Gemini as the LLM provider.

## Context

The AI agent must decide which tools to call, execute them, interpret results, and potentially call additional tools in a loop before generating a final response. This requires a structured workflow, not a single LLM API call.

## Decision

Use **LangGraph** `StateGraph` API for the agent graph. Use **Google Gemini** (gemini-3.6-flash) as the LLM provider.

## Alternatives Considered

### Agent Framework

| Option | Rejected Because |
|---|---|
| Raw LLM API call | No tool loop; single-shot only |
| LangChain `AgentExecutor` | Legacy API; LangGraph is the recommended successor |
| Custom tool loop | Re-invents what LangGraph provides; harder to maintain |
| CrewAI / AutoGen | Multi-agent frameworks; unnecessary complexity for a single agent |

### LLM Provider

| Option | Rejected Because |
|---|---|
| OpenAI (GPT-4o) | Cost; free tier insufficient for iterative development |
| Anthropic (Claude) | Tool-calling support less mature at time of decision |
| Local LLM | Insufficient quality for reliable tool-calling |

## Rationale

- LangGraph provides the exact `agent_node → tool_node → agent_node` loop needed
- Built-in checkpointing (MemorySaver) for conversation state
- Built-in streaming support compatible with tool execution
- Gemini's free tier enables cost-free development and demo

## Consequences

### Benefits
- Real tool-calling graph (not single-shot)
- Checkpointed conversation state without custom code
- Streaming compatible with tool execution
- No API costs during development

### Costs
- LangGraph API is evolving; minor breaking changes possible
- Gemini tool-calling may be slightly less reliable than GPT-4o (mitigated by clear schemas and system prompt)

---

# ADR-007: pgvector for Vector Storage

**Status**: Accepted
**Date**: 2026-08-17
**Decision**: Use pgvector (PostgreSQL extension) instead of a dedicated vector database.

## Context

RAG requires storing document chunk embeddings and performing cosine similarity searches. The options are: use a dedicated vector DB (Pinecone, Weaviate, Qdrant, Milvus) or use pgvector within PostgreSQL.

## Decision

Use **pgvector** with HNSW indexing inside the existing PostgreSQL instance.

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| Pinecone | Managed service adds external dependency and cost |
| Weaviate | Separate infrastructure to manage |
| Qdrant | Separate infrastructure to manage |
| FAISS | In-memory only; not persistent; no SQL integration |
| ChromaDB | Additional dependency; doesn't integrate with existing PostgreSQL |

## Rationale

- **No additional infrastructure** — vectors live in the same PostgreSQL that stores everything else
- **ACID transactions** — chunk storage is transactional with document records
- **Single backup** — one database to back up
- **Sufficient scale** — a handful of 10-K PDFs produces <100K chunks; pgvector handles this easily
- **HNSW index** — provides good approximate nearest neighbor performance
- **Interview answer**: "I used pgvector because the vector volume doesn't justify a separate system. PostgreSQL handles relational data, JSON, and vectors in one database."

### Embedding Configuration

| Property | Value |
|---|---|
| Provider | Google Gemini |
| Model | gemini-embedding-2 |
| Dimension | 768 |
| Distance metric | Cosine |
| Index type | HNSW |

## Consequences

### Benefits
- Zero additional infrastructure
- Transactional consistency between documents and chunks
- Single connection pool and backup
- Simple development and deployment

### Costs
- Lower performance than dedicated vector DBs at >1M vectors
- Fewer vector-specific features (no hybrid search, no metadata filtering beyond SQL WHERE)

### Scale Threshold
If the project eventually needs >1M vectors or sub-millisecond vector search, migration to a dedicated vector DB is feasible since the retrieval interface is behind `RetrievalService`.
