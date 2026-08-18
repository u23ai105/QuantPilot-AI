"""get_performance_metrics tool — Retrieve metrics for a completed backtest.

Returns authoritative stored results.  Never independently recomputes
metrics.  Respects all backtest statuses (QUEUED, RUNNING, COMPLETED,
FAILED).
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.ai.tools.schemas import GetPerformanceMetricsInput


@tool(args_schema=GetPerformanceMetricsInput)
async def get_performance_metrics(
    backtest_id: int,
    **kwargs,
) -> dict:
    """Retrieve performance metrics for a backtest.

    Returns the current status and metrics if the backtest is completed.
    """
    from app.ai.tools._context import get_current_user_id, get_db_session_for_tool
    from app.services.backtest_service import BacktestService

    user_id = get_current_user_id()

    session = await get_db_session_for_tool()
    try:
        service = BacktestService(session)
        backtest = await service.get_backtest_with_result(backtest_id)

        if not backtest:
            return {"error": f"Backtest {backtest_id} not found."}

        # Verify ownership: backtest -> strategy -> user
        if backtest.strategy.user_id != user_id:
            return {"error": "You do not have access to this backtest."}

        result_data: dict = {
            "backtest_id": backtest.id,
            "status": backtest.status,
            "metrics": None,
        }

        if backtest.status == "FAILED":
            result_data["error"] = backtest.error_message or "Backtest failed"
        elif backtest.status == "COMPLETED" and backtest.result:
            r = backtest.result
            result_data["metrics"] = {
                "total_return": float(r.total_return) if r.total_return is not None else None,
                "cagr": float(r.cagr) if r.cagr is not None else None,
                "volatility": float(r.volatility) if r.volatility is not None else None,
                "sharpe_ratio": float(r.sharpe_ratio) if r.sharpe_ratio is not None else None,
                "sortino_ratio": float(r.sortino_ratio) if r.sortino_ratio is not None else None,
                "max_drawdown": float(r.max_drawdown) if r.max_drawdown is not None else None,
                "win_rate": float(r.win_rate) if r.win_rate is not None else None,
                "total_trades": r.total_trades,
            }

        return result_data
    finally:
        await session.close()
