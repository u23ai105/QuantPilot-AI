# Phase 6: Evaluation Harness (Completed)

## Overview
Phase 6 introduced the deterministic evaluation harness designed to objectively measure the performance of the AI Agent and the RAG infrastructure. We built a framework to evaluate Retrieval Hit@K, Citation Accuracy, and Answer Quality without relying on an "LLM-as-a-judge" approach.

## Implementation Details
1. **Benchmark PDF:** A synthetically generated 5-page financial benchmark report (`tests/fixtures/benchmark_report.pdf`) was created once and committed.
2. **Evaluation Questions:** 15 manually curated questions with exact deterministic answers and expected page numbers were seeded.
3. **Database Schema:** `EvalQuestion` and `EvalRun` models were added, storing evaluation configuration and preserving `retrieved_sources_json` for provenance. An additional field `canonical_format_hit` was added to decouple semantic citation accuracy from strict string formatting.
4. **Deterministic Service:** `EvalService` implements string normalization, numeric parsing, a 5% tolerance window for numeric answers, and checks retrieval inclusion deterministically. It distinguishes between **Citation Accuracy** (correct document and page) and **Canonical Format Compliance** (using the exact `[Source: X, Page: Y]` vs alternative brackets like `【`).

## Architecture Verification
- **Groq usage restricted to Evaluation:** The Groq (`openai/gpt-oss-120b`) provider was successfully integrated exclusively for the `scripts/run_eval.py` evaluation suite.
- **Gemini remains production provider:** The `app/ai/provider.py` and `app/ai/graph.py` architecture was confirmed untouched. Gemini continues to serve as the production system provider.

## Live Evaluation Results (Final Verified)
The final live evaluation was executed using the Groq evaluation-only pathway. 

- **Retrieval Hit@5:** 15/15 (100.0%)
- **Citation Accuracy:** 15/15 (100.0%)
- **Answer Quality:** 15/15 (100.0%)
- **Canonical Format Compliance:** 8/15 (53.3%)
- **Successful generations:** 15/15
- **API failures:** 0

**Analysis:**
- **Clear distinction between semantic citation correctness and formatting compliance:** The model semantically cited the correct document and exact page for 100% of the questions. However, the model correctly followed the *exact* canonical bracket format 53.3% of the time, often using alternative brackets (e.g., Unicode corner brackets `【`). The two metrics successfully reflect this difference.
- **100% Retrieval Hit@5:** Validates the underlying `pgvector` indexing and similarity search pipeline.
- **100% Answer Quality:** The deterministically tuned parsing correctly extracts values and accounts for the 5% error tolerance requirement.

## Verification & Security
- **Security Audit:** No API keys are tracked in git (`.env` is properly ignored). The compromised Groq key from terminal history was replaced and isolated.
- **Test Suite:** 61/61 tests pass.
- **Linters:** `ruff` (check and format) passes cleanly.
