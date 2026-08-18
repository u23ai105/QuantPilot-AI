# ADR-002: Clean Architecture / Hexagonal Principles

**Status**: Accepted
**Date**: 2026-08-17
**Decision**: Apply Clean Architecture / Hexagonal Architecture principles for internal module layering.

## Context

QuantPilot AI has multiple external dependencies (PostgreSQL, Redis, yfinance, Gemini LLM, Gemini Embeddings). Without architectural boundaries, business logic becomes tightly coupled to these systems, making testing difficult and provider changes expensive.

## Decision

Enforce the following dependency direction:

```text
API Layer → Application Services → Domain Logic → Ports (Interfaces) ← Infrastructure (Adapters)
```

### Rules

1. **Domain layer** (`app/domain/`) has **zero** imports from `api/`, `models/`, `repositories/`, `infrastructure/`, `ai/`, or `workers/`
2. External systems are accessed through **adapter interfaces** (Protocols)
3. **Services** orchestrate domain logic and infrastructure, but don't contain business rules themselves
4. **Repositories** encapsulate all database access behind methods

### Adapter Interfaces

| Interface | Implementation | Hides |
|---|---|---|
| `EmbeddingProvider` | `GeminiEmbeddingAdapter` | Gemini embedding SDK |
| `LLMProvider` | `GeminiLLMAdapter` | Gemini LLM SDK |
| `YFinanceAdapter` | (concrete class) | yfinance library |

## Consequences

### Benefits
- Pure unit tests for all quant calculations (no database needed)
- Embedding and LLM providers are swappable without touching services
- Clear mental model for "where does this code belong?"
- Demonstrates dependency inversion in interviews

### Costs
- More files than a flat structure
- Some adapters have only one implementation (acceptable tradeoff for clarity)

### What This Is NOT
- Not a multi-provider abstraction — one adapter per external system
- Not over-applied DDD — no aggregate roots with complex lifecycle rules where unnecessary
