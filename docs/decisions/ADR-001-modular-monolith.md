# ADR-001: Modular Monolith Architecture

**Status**: Accepted
**Date**: 2026-08-17
**Decision**: Use a modular monolith architecture instead of microservices.

## Context

QuantPilot AI is an SDE + GenAI interview project built by a single developer. The system includes API, background workers, AI agent, and RAG — all within a single codebase.

## Decision

Adopt a **modular monolith** with clean internal boundaries (API → Service → Repository layering) rather than microservices.

## Consequences

### Benefits
- **Single deployment unit** — one Docker image, one codebase, simpler debugging
- **No inter-service communication overhead** — direct function calls instead of HTTP/gRPC
- **Simpler transactions** — database transactions don't cross service boundaries
- **Faster development** — no need to manage multiple repos, APIs, or deployments
- **Appropriate for team size** — one developer does not benefit from microservice isolation

### Risks
- Module boundaries must be enforced by convention (package structure, dependency direction) rather than network boundaries
- All modules share one database, one process (except Celery workers)

### Why Not Microservices
- No team requiring independent deployment
- No need for polyglot services
- Adds Kubernetes, service mesh, distributed tracing — all explicitly out of scope
- Interview credibility comes from depth of implementation, not infrastructure complexity

### Future Path
Individual modules (e.g., AI agent, backtest engine) could be extracted into separate services if the team or traffic grows. The clean layering makes this possible without rewriting business logic.
