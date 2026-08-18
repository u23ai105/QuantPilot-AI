import asyncio
import logging
from datetime import date

from sqlalchemy import select

from app.core.db import async_session_maker
from app.models.ticker import Ticker
from app.models.user import User
from app.schemas.backtests import BacktestCreate
from app.schemas.strategies import (
    StrategyCondition,
    StrategyCreate,
    StrategyLogicGroup,
    StrategyPositionSizing,
    StrategyRules,
)
from app.services.backtest_service import BacktestService
from app.services.strategy_service import StrategyService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_e2e():
    async with async_session_maker() as session:
        import uuid

        stmt_u = select(User).where(User.email == "test_e2e@quantpilot.ai")
        res_u = await session.execute(stmt_u)
        user = res_u.scalar_one_or_none()
        if not user:
            user = User(email="test_e2e@quantpilot.ai", hashed_password="hashed")
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # 1. Create Strategy
        strat_service = StrategyService(session)
        rules = StrategyRules(
            version=1,
            entry=StrategyLogicGroup(
                conditions=[StrategyCondition(indicator="sma", params={"period": 10}, operator="crosses_above", against=0.0)], logic="AND"
            ),
            exit=StrategyLogicGroup(conditions=[StrategyCondition(indicator="rsi", params={"period": 14}, operator="gt", against=70.0)], logic="AND"),
            position_sizing=StrategyPositionSizing(type="fixed_fraction", value=1.0),
        )
        strat_create = StrategyCreate(name=f"E2E SMA {uuid.uuid4().hex[:6]}", rules_json=rules)
        strategy = await strat_service.create_strategy(user.id, strat_create)
        logger.info(f"Created strategy: {strategy.id}")

        # 2. POST Backtest
        from datetime import timedelta

        from app.services.market_data_service import MarketDataService

        md_service = MarketDataService(session)
        end_date = date.today()
        start_date = end_date - timedelta(days=300)

        stmt_t = select(Ticker).where(Ticker.symbol == "AAPL")
        res_t = await session.execute(stmt_t)
        ticker = res_t.scalar_one_or_none()
        if not ticker:
            logger.info("Ingesting AAPL market data for E2E test...")
            await md_service.ingest_ticker("AAPL", start_date - timedelta(days=100), end_date)

        bt_service = BacktestService(session)
        bt_create = BacktestCreate(
            strategy_id=strategy.id,
            symbol="AAPL",
            start_date=start_date,
            end_date=end_date,
            initial_capital=10000.0,
            commission=0.001,
            slippage=0.0005,
        )

        try:
            backtest = await bt_service.create_backtest(user.id, bt_create)
            logger.info(f"Created backtest: {backtest.id}, Task ID: {backtest.celery_task_id}, Status: {backtest.status}")
        except Exception as e:
            logger.error(f"Failed to create backtest (maybe missing AAPL?): {e}")
            return

        # Poll for completion
        logger.info("Polling for Celery worker completion...")
        for _ in range(30):
            await asyncio.sleep(2)
            async with async_session_maker() as poll_session:
                poll_bt_service = BacktestService(poll_session)
                bt_check = await poll_bt_service.get_backtest_with_result(backtest.id)
                logger.info(f"Status: {bt_check.status}")
                if bt_check.status in ["COMPLETED", "FAILED"]:
                    if bt_check.status == "COMPLETED":
                        res = bt_check.result
                        logger.info("Backtest COMPLETED successfully!")
                        logger.info(f"Total Return: {res.total_return}")
                        logger.info(f"CAGR: {res.cagr}")
                        logger.info(f"Volatility: {res.volatility}")
                        logger.info(f"Sharpe Ratio: {res.sharpe_ratio}")
                        logger.info(f"Sortino Ratio: {res.sortino_ratio}")
                        logger.info(f"Max Drawdown: {res.max_drawdown}")
                        logger.info(f"Win Rate: {res.win_rate}")
                        logger.info(f"Total Trades: {res.total_trades}")
                    else:
                        logger.error(f"Backtest FAILED: {bt_check.error_message}")
                    return

        logger.error("Backtest timed out.")


if __name__ == "__main__":
    asyncio.run(run_e2e())
