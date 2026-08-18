"""run_backtest tool — Submit a strategy backtest for async execution.

Thin wrapper that delegates to BacktestService.  Verifies strategy
ownership via the authenticated user context.
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.ai.tools.schemas import RunBacktestInput


@tool(args_schema=RunBacktestInput)
async def run_backtest(
    strategy_id: int,
    symbol: str,
    start: str = "",
    end: str = "",
    **kwargs,
) -> dict:
    """Submit a strategy backtest for asynchronous execution.

    Returns a backtest_id and QUEUED status.  Use get_performance_metrics
    with the backtest_id to check results later.
    """
    from datetime import date as date_type

    from app.ai.tools._context import get_current_user_id, get_db_session_for_tool
    from app.schemas.backtests import BacktestCreate
    from app.services.backtest_service import BacktestService

    start_date = date_type.fromisoformat(str(start))
    end_date = date_type.fromisoformat(str(end))
    user_id = get_current_user_id()

    session = await get_db_session_for_tool()
    try:
        service = BacktestService(session)
        data = BacktestCreate(
            strategy_id=strategy_id,
            symbol=symbol.upper(),
            start_date=start_date,
            end_date=end_date,
        )
        backtest = await service.create_backtest(user_id, data)

        return {
            "backtest_id": backtest.id,
            "status": backtest.status,
            "message": (f"Backtest submitted. Use get_performance_metrics with backtest_id={backtest.id} to retrieve results."),
        }
    finally:
        await session.close()
