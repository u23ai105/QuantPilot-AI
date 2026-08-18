"""get_market_data tool — Retrieve OHLCV data for a symbol.

Thin wrapper that delegates to MarketDataService.  Contains no
business logic or SQL.
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.ai.tools.schemas import GetMarketDataInput


@tool(args_schema=GetMarketDataInput)
async def get_market_data(
    symbol: str,
    start: str,
    end: str,
    **kwargs,
) -> dict:
    """Retrieve OHLCV price data for a ticker symbol within a date range.

    Use this when users ask about stock prices or price history.
    """
    # Import here to avoid circular imports at module level
    from datetime import date as date_type

    from app.ai.tools._context import get_db_session_for_tool
    from app.services.market_data_service import MarketDataService

    start_date = date_type.fromisoformat(str(start))
    end_date = date_type.fromisoformat(str(end))

    session = await get_db_session_for_tool()
    try:
        service = MarketDataService(session)
        records = await service.get_ohlcv(symbol, start_date, end_date)

        bars = [
            {
                "date": str(r.date),
                "open": float(r.open),
                "high": float(r.high),
                "low": float(r.low),
                "close": float(r.close),
                "volume": int(r.volume),
            }
            for r in records
        ]

        return {
            "symbol": symbol.upper(),
            "bars": bars[:50],  # Limit response size for LLM context
            "count": len(records),
            "note": f"Showing {min(len(bars), 50)} of {len(records)} bars" if len(records) > 50 else None,
        }
    finally:
        await session.close()
