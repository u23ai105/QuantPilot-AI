"""Tests for AI tool schemas and tool delegation logic.

These tests use mocked services — no live Gemini API or database.
"""

from datetime import date

import pytest

from app.ai.tools.schemas import (
    CalculateIndicatorsInput,
    GetMarketDataInput,
    GetPerformanceMetricsInput,
    RunBacktestInput,
    SearchDocumentsInput,
)

# ─── Schema validation tests ────────────────────────────────────────────


def test_get_market_data_schema():
    schema = GetMarketDataInput(symbol="AAPL", start=date(2024, 1, 1), end=date(2024, 6, 1))
    assert schema.symbol == "AAPL"
    assert schema.start == date(2024, 1, 1)
    assert schema.end == date(2024, 6, 1)


def test_calculate_indicators_schema():
    schema = CalculateIndicatorsInput(
        symbol="AAPL",
        indicator="rsi",
        params={"period": 14},
        start=date(2024, 1, 1),
        end=date(2024, 6, 1),
    )
    assert schema.indicator == "rsi"
    assert schema.params == {"period": 14}


def test_calculate_indicators_schema_defaults():
    schema = CalculateIndicatorsInput(
        symbol="AAPL",
        indicator="sma",
        start=date(2024, 1, 1),
        end=date(2024, 6, 1),
    )
    assert schema.params == {}


def test_run_backtest_schema():
    schema = RunBacktestInput(
        strategy_id=1,
        symbol="AAPL",
        start=date(2024, 1, 1),
        end=date(2024, 6, 1),
    )
    assert schema.strategy_id == 1


def test_get_performance_metrics_schema():
    schema = GetPerformanceMetricsInput(backtest_id=42)
    assert schema.backtest_id == 42


def test_search_documents_schema():
    schema = SearchDocumentsInput(query="Apple revenue 2023")
    assert schema.query == "Apple revenue 2023"
    assert schema.document_id is None


def test_search_documents_schema_with_doc_id():
    schema = SearchDocumentsInput(query="revenue", document_id=5)
    assert schema.document_id == 5


# ─── search_documents stub test ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_documents_stub():
    """search_documents should return UNAVAILABLE in Phase 4."""
    from app.ai.tools.documents import search_documents

    result = await search_documents.ainvoke({"query": "Apple revenue", "document_id": None})
    assert result["status"] == "UNAVAILABLE"
    assert result["count"] == 0
    assert result["results"] == []
