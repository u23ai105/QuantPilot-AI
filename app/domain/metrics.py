import math
from datetime import datetime
from typing import Any

import pandas as pd
from pydantic import BaseModel


class ValidationError(Exception):
    pass


class MetricsResult(BaseModel):
    total_return: float
    cagr: float
    volatility: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown: float
    win_rate: float | None
    total_trades: int
    equity_curve: list[dict[str, Any]]
    trades: list[dict[str, Any]]


class MetricsCalculator:
    @staticmethod
    def calculate(
        initial_capital: float,
        equity_curve: pd.DataFrame,
        trades: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
    ) -> MetricsResult:
        elapsed_days = (end_date - start_date).days
        if elapsed_days <= 0:
            raise ValidationError("elapsed_days must be > 0")

        # Basic Stats
        final_equity = equity_curve["Equity"].iloc[-1] if not equity_curve.empty else initial_capital
        total_return = (final_equity / initial_capital) - 1.0

        cagr = ((final_equity / initial_capital) ** (365.25 / elapsed_days)) - 1.0

        # Daily Returns
        # We need daily equity to compute daily_pct_change.
        # backtesting.py equity_curve index is datetime, but it might not be strictly daily.
        # We resample to daily or use it as is? "daily_pct_change" usually means bar-to-bar if daily data.
        # Let's assume daily data as per Phase 2.
        daily_pct_change = equity_curve["Equity"].pct_change().dropna()

        # Volatility
        volatility = None
        if not daily_pct_change.empty:
            std_dev = daily_pct_change.std(ddof=1)
            if pd.notna(std_dev) and std_dev > 0.0:
                volatility = std_dev * math.sqrt(252)

        # Sharpe Ratio
        sharpe_ratio = None
        if volatility is not None and volatility > 0.0:
            sharpe_ratio = (daily_pct_change.mean() / std_dev) * math.sqrt(252)

        # Sortino Ratio
        sortino_ratio = None
        if not daily_pct_change.empty:
            # downside deviation = sqrt(mean(min(daily_returns - 0.0, 0)^2))
            # which is sqrt(mean(downside_returns^2))
            # Standard definition: downside deviation uses N = total number of periods, not just downside periods.
            # "mean(min(daily_returns - 0.0, 0)^2)" implies sum(min(...)^2) / total_periods
            downside_sq = (daily_pct_change.clip(upper=0.0) ** 2).mean()
            downside_deviation = math.sqrt(downside_sq)

            if downside_deviation > 0.0:
                sortino_ratio = (daily_pct_change.mean() / downside_deviation) * math.sqrt(252)

        # Max Drawdown
        max_drawdown = 0.0
        if not equity_curve.empty:
            running_max = equity_curve["Equity"].cummax()
            drawdowns = (equity_curve["Equity"] - running_max) / running_max
            min_dd = drawdowns.min()
            if pd.notna(min_dd):
                max_drawdown = abs(float(min_dd))

        # Win Rate
        total_closed_trades = len(trades)
        win_rate = None
        if total_closed_trades > 0:
            # Break-even trades (pnl == 0.0) are NOT winning trades
            winning_trades = len(trades[trades["PnL"] > 0.0])
            win_rate = winning_trades / total_closed_trades

        # Format JSON outputs
        # equity_curve format: list of {date, value}
        eq_list = []
        for dt, row in equity_curve.iterrows():
            eq_list.append({"date": dt.isoformat(), "value": float(row["Equity"])})

        # trades format: array of trade records
        tr_list = []
        for _, tr in trades.iterrows():
            tr_list.append(
                {
                    "entry_time": tr["EntryTime"].isoformat() if pd.notna(tr.get("EntryTime")) else None,
                    "exit_time": tr["ExitTime"].isoformat() if pd.notna(tr.get("ExitTime")) else None,
                    "entry_price": float(tr["EntryPrice"]),
                    "exit_price": float(tr["ExitPrice"]),
                    "size": int(tr["Size"]),
                    "pnl": float(tr["PnL"]),
                    "return_pct": float(tr["ReturnPct"]),
                }
            )

        return MetricsResult(
            total_return=float(total_return),
            cagr=float(cagr),
            volatility=float(volatility) if volatility is not None else None,
            sharpe_ratio=float(sharpe_ratio) if sharpe_ratio is not None else None,
            sortino_ratio=float(sortino_ratio) if sortino_ratio is not None else None,
            max_drawdown=float(max_drawdown),
            win_rate=float(win_rate) if win_rate is not None else None,
            total_trades=total_closed_trades,
            equity_curve=eq_list,
            trades=tr_list,
        )
