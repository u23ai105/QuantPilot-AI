import asyncio
import logging
from datetime import timedelta

import pandas as pd
from backtesting import Backtest as BtEngine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.domain.metrics import MetricsCalculator
from app.domain.strategy_interpreter import StrategyInterpreter
from app.models.backtest import BacktestResult
from app.models.strategy import Strategy
from app.repositories.backtest_repo import BacktestRepository
from app.repositories.market_data_repo import MarketDataRepository
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def execute_backtest_async(backtest_id: int):
    # Create an engine bound to the current asyncio event loop
    task_engine = create_async_engine(settings.database_url, echo=(settings.app_env == "development"))
    task_session_maker = async_sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with task_session_maker() as session:
            bt_repo = BacktestRepository(session)
            md_repo = MarketDataRepository(session)

            # 1. Atomic Ownership Check
            claimed = await bt_repo.claim_execution(backtest_id)
            if not claimed:
                logger.info(f"Backtest {backtest_id} already claimed or completed.")
                return

            try:
                # 2. Load Backtest
                backtest = await bt_repo.get_by_id(backtest_id)
                if not backtest:
                    return

                # Load Strategy
                strategy = await session.get(Strategy, backtest.strategy_id)

                # 3. Load OHLCV data with warmup
                warmup_days = 100
                fetch_start = backtest.start_date - timedelta(days=warmup_days)
                ohlcv_records = await md_repo.get_ohlcv(ticker_id=backtest.ticker_id, start=fetch_start, end=backtest.end_date)

                if not ohlcv_records:
                    raise ValueError("No market data found for the given date range.")

                # Convert to backtesting.py DataFrame format
                df = pd.DataFrame(
                    [
                        {
                            "Open": float(r.open),
                            "High": float(r.high),
                            "Low": float(r.low),
                            "Close": float(r.close),
                            "Volume": int(r.volume),
                        }
                        for r in ohlcv_records
                    ],
                    index=[r.date for r in ohlcv_records],
                )
                df.index = pd.to_datetime(df.index)

                # 4. Interpret strategy
                interpreter = StrategyInterpreter()
                StrategyClass = interpreter.interpret(strategy.rules_json)

                # We must prevent trading before the actual start_date due to warmup
                # We can dynamically subclass to override next()
                OriginalNext = StrategyClass.next

                def next_with_warmup(self):
                    # Skip trading before actual start date
                    if self.data.index[-1].date() < backtest.start_date:
                        return
                    OriginalNext(self)

                StrategyClass.next = next_with_warmup

                # 5. Execute backtest
                bt = BtEngine(
                    df,
                    StrategyClass,
                    cash=float(backtest.initial_capital),
                    commission=float(backtest.commission),
                    spread=float(backtest.slippage),
                    margin=1.0,
                    trade_on_close=False,
                    exclusive_orders=True,
                )

                bt_result = bt.run()

                # 6. Calculate metrics
                metrics = MetricsCalculator.calculate(
                    initial_capital=float(backtest.initial_capital),
                    equity_curve=bt_result._equity_curve,
                    trades=bt_result._trades,
                    start_date=backtest.start_date,
                    end_date=backtest.end_date,
                )

                # 7. INSERT backtest_results + UPDATE status
                result_model = BacktestResult(
                    total_return=metrics.total_return,
                    cagr=metrics.cagr,
                    volatility=metrics.volatility,
                    sharpe_ratio=metrics.sharpe_ratio,
                    sortino_ratio=metrics.sortino_ratio,
                    max_drawdown=metrics.max_drawdown,
                    win_rate=metrics.win_rate,
                    total_trades=metrics.total_trades,
                    equity_curve_json=metrics.equity_curve,
                    trades_json=metrics.trades,
                )

                await bt_repo.save_result(backtest_id, result_model)

            except Exception as e:
                logger.exception(f"Backtest {backtest_id} failed: {e}")
                await bt_repo.update_status(backtest_id, "FAILED", error_message=str(e))
    finally:
        await task_engine.dispose()


@celery_app.task(name="tasks.run_backtest", bind=True)
def run_backtest_task(self, backtest_id: int):
    asyncio.run(execute_backtest_async(backtest_id))
