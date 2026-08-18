import math
from datetime import datetime, timedelta

import pandas as pd
import pytest

from app.domain.metrics import MetricsCalculator, ValidationError


def test_metrics_known_answers():
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 31)
    # 30 days elapsed

    # 1. Total Return and CAGR
    # Initial: 10000, Final: 11000 -> TR = 10%, CAGR = (1.1)^(365.25/30) - 1
    initial_capital = 10000.0
    equity_curve = pd.DataFrame({"Equity": [10000.0, 10500.0, 11000.0]}, index=[start_date, start_date + timedelta(days=15), end_date])

    # Let's add some trades
    trades = pd.DataFrame(
        {
            "Size": [100, 100],
            "EntryBar": [0, 1],
            "ExitBar": [1, 2],
            "EntryPrice": [100.0, 105.0],
            "ExitPrice": [105.0, 110.0],
            "PnL": [500.0, 500.0],
            "ReturnPct": [0.05, 0.0476],
            "EntryTime": [start_date, start_date + timedelta(days=15)],
            "ExitTime": [start_date + timedelta(days=15), end_date],
            "Duration": [timedelta(days=15), timedelta(days=15)],
        }
    )

    metrics = MetricsCalculator.calculate(initial_capital, equity_curve, trades, start_date, end_date)

    assert math.isclose(metrics.total_return, 0.1)

    expected_cagr = (1.1 ** (365.25 / 30)) - 1
    assert math.isclose(metrics.cagr, expected_cagr)

    assert metrics.win_rate == 1.0
    assert metrics.total_trades == 2


def test_metrics_edge_cases():
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 31)

    # Zero closed trades
    equity_curve = pd.DataFrame({"Equity": [10000.0]}, index=[start_date])
    trades = pd.DataFrame(columns=["Size", "EntryBar", "ExitBar", "EntryPrice", "ExitPrice", "PnL", "ReturnPct", "EntryTime", "ExitTime", "Duration"])

    metrics = MetricsCalculator.calculate(10000.0, equity_curve, trades, start_date, end_date)

    assert metrics.win_rate is None
    assert metrics.total_trades == 0
    assert metrics.total_return == 0.0

    # Zero return volatility
    equity_curve_flat = pd.DataFrame(
        {"Equity": [10000.0, 10000.0, 10000.0]}, index=[start_date, start_date + timedelta(days=1), start_date + timedelta(days=2)]
    )

    metrics_flat = MetricsCalculator.calculate(10000.0, equity_curve_flat, trades, start_date, end_date)

    # Pct change of [10000, 10000, 10000] is [0, 0] -> std is 0
    assert metrics_flat.volatility is None
    assert metrics_flat.sharpe_ratio is None
    assert metrics_flat.sortino_ratio is None

    # Elapsed days <= 0
    with pytest.raises(ValidationError):
        MetricsCalculator.calculate(10000.0, equity_curve, trades, start_date, start_date)


def test_win_rate_break_even():
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 31)
    equity_curve = pd.DataFrame({"Equity": [10000.0]}, index=[start_date])

    trades = pd.DataFrame(
        {
            "Size": [100, 100, 100],
            "EntryBar": [0, 1, 2],
            "ExitBar": [1, 2, 3],
            "EntryPrice": [100.0, 105.0, 110.0],
            "ExitPrice": [105.0, 105.0, 100.0],
            "PnL": [500.0, 0.0, -1000.0],
            "ReturnPct": [0.05, 0.0, -0.09],
            "EntryTime": [start_date, start_date, start_date],
            "ExitTime": [start_date, start_date, start_date],
            "Duration": [timedelta(days=1)] * 3,
        }
    )

    metrics = MetricsCalculator.calculate(10000.0, equity_curve, trades, start_date, end_date)

    # Total trades = 3. Winning = 1 (pnl > 0). Break-even is 0. Losing is 1.
    # Win rate = 1 / 3 = 0.3333
    assert math.isclose(metrics.win_rate, 1 / 3)
