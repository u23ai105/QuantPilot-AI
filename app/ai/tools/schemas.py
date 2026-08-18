"""Structured input/output schemas for all agent tools.

Every tool uses explicit typed schemas to bound LLM hallucination
before reaching the service layer.  Schemas are Pydantic BaseModel
sub-classes compatible with Gemini function-calling.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

# ── Tool 1: get_market_data ──────────────────────────────────────────────


class GetMarketDataInput(BaseModel):
    """Input schema for the get_market_data tool."""

    symbol: str = Field(description="Ticker symbol, e.g. 'AAPL'")
    start: date = Field(description="Start date (inclusive), YYYY-MM-DD")
    end: date = Field(description="End date (inclusive), YYYY-MM-DD")


# ── Tool 2: calculate_indicators ─────────────────────────────────────────


class CalculateIndicatorsInput(BaseModel):
    """Input schema for the calculate_indicators tool."""

    symbol: str = Field(description="Ticker symbol, e.g. 'AAPL'")
    indicator: str = Field(description="One of: sma, ema, rsi, macd, bollinger, atr")
    params: dict = Field(
        default_factory=dict,
        description=(
            "Indicator-specific parameters.  "
            "sma/ema/rsi/atr: {period: int}. "
            "macd: {fast: int, slow: int, signal: int}. "
            "bollinger: {period: int, std_dev: float}."
        ),
    )
    start: date = Field(description="Start date (inclusive), YYYY-MM-DD")
    end: date = Field(description="End date (inclusive), YYYY-MM-DD")


# ── Tool 3: run_backtest ─────────────────────────────────────────────────


class RunBacktestInput(BaseModel):
    """Input schema for the run_backtest tool."""

    strategy_id: int = Field(description="ID of the saved strategy")
    symbol: str = Field(description="Ticker symbol to backtest on")
    start: date = Field(description="Backtest start date, YYYY-MM-DD")
    end: date = Field(description="Backtest end date, YYYY-MM-DD")


# ── Tool 4: get_performance_metrics ──────────────────────────────────────


class GetPerformanceMetricsInput(BaseModel):
    """Input schema for the get_performance_metrics tool."""

    backtest_id: int = Field(description="ID of the backtest to query")


# ── Tool 5: search_documents ────────────────────────────────────────────


class SearchDocumentsInput(BaseModel):
    """Input schema for the search_documents tool."""

    query: str = Field(description="Natural language search query")
    document_id: int | None = Field(default=None, description="Optional: restrict to a specific document")
