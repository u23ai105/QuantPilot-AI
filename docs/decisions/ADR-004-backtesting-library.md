# ADR-004: backtesting.py as Backtest Engine

**Status**: Accepted
**Date**: 2026-08-17
**Decision**: Use `backtesting.py` instead of `vectorbt` for strategy backtesting.

## Context

The project needs a backtesting engine to execute declarative strategies against historical OHLCV data.

## Decision

Use **backtesting.py**.

## Alternatives Considered

| Library | Pros | Cons |
|---|---|---|
| **backtesting.py** | Simple API, fast to learn, good docs, event-driven | Non-vectorized, fewer built-in features |
| **vectorbt** | Vectorized (fast), feature-rich, built-in metrics | Unusual API, steep learning curve, complex indexing |

## Rationale

- vectorbt's API conventions would take real days to learn — that time is better invested in the AI/RAG layer where the project's differentiation lives
- backtesting.py correctly implements a backtest loop with buy/sell signals, commission, equity tracking
- Interview answer: "I chose the simpler library because my differentiation is in the AI layer, not backtest engine internals"
- This choice is explicitly locked in the project plan

## Consequences

### Benefits
- Faster implementation (~days saved)
- Simpler code to explain in interviews
- Less library-specific complexity to debug

### Costs
- Non-vectorized execution (acceptable for single-ticker backtests at this scale)
- Fewer built-in metrics (supplemented by custom `MetricsCalculator`)
- No multi-asset backtesting (out of scope anyway)
