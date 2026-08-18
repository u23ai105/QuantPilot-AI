"""calculate_indicators tool — Calculate technical indicators for a symbol.

Thin wrapper that delegates to IndicatorService.  Contains no
business logic or SQL.
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.ai.tools.schemas import CalculateIndicatorsInput


@tool(args_schema=CalculateIndicatorsInput)
async def calculate_indicators(
    symbol: str,
    indicator: str,
    params: dict | None = None,
    start: str = "",
    end: str = "",
    **kwargs,
) -> dict:
    """Calculate a technical indicator for a ticker symbol.

    Supported indicators: sma, ema, rsi, macd, bollinger, atr.
    """
    from datetime import date as date_type

    from app.ai.tools._context import get_db_session_for_tool
    from app.services.indicator_service import IndicatorService

    params = params or {}
    start_date = date_type.fromisoformat(str(start))
    end_date = date_type.fromisoformat(str(end))

    session = await get_db_session_for_tool()
    try:
        service = IndicatorService(session)
        dates, values = await service.calculate(
            symbol=symbol,
            indicator=indicator,
            params=params,
            start=start_date,
            end=end_date,
        )

        # Format output
        data = []
        for d, v in zip(dates, values):
            if isinstance(v, dict):
                data.append({"date": str(d), "values": {k: round(float(val), 4) for k, val in v.items()}})
            else:
                data.append({"date": str(d), "value": round(float(v), 4)})

        return {
            "symbol": symbol.upper(),
            "indicator": indicator.lower(),
            "params": params,
            "data": data[:50],  # Limit for LLM context
            "count": len(dates),
        }
    finally:
        await session.close()
