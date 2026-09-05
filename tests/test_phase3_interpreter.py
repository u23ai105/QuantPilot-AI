import numpy as np
import pandas as pd
from backtesting import Backtest
from backtesting._util import _strategy_indicators

from app.domain.strategy_interpreter import StrategyInterpreter


def _synthetic_ohlcv(n: int = 300) -> pd.DataFrame:
    # Oscillating price so a fast/slow SMA pair crosses repeatedly and trades must occur.
    t = np.arange(n)
    close = 200 + 20 * np.sin(t / 12.0) + t * 0.05
    return pd.DataFrame(
        {
            "Open": close * 0.999,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": np.full(n, 1_000_000),
        },
        index=pd.date_range("2025-01-02", periods=n, freq="B"),
    )


_SMA_CROSS_RULES = {
    "version": 1,
    "entry": {
        "logic": "AND",
        "conditions": [
            {
                "indicator": "sma",
                "params": {"period": 5},
                "operator": "crosses_above",
                "against": {"indicator": "sma", "params": {"period": 20}},
            }
        ],
    },
    "exit": {
        "logic": "AND",
        "conditions": [
            {
                "indicator": "sma",
                "params": {"period": 5},
                "operator": "crosses_below",
                "against": {"indicator": "sma", "params": {"period": 20}},
            }
        ],
    },
    "position_sizing": {"type": "fixed_fraction", "value": 0.95},
}


def test_interpreter_execution():
    # Provide dummy data
    data = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
            "High": [105.0, 106.0, 107.0, 108.0, 109.0, 110.0],
            "Low": [95.0, 96.0, 97.0, 98.0, 99.0, 100.0],
            "Close": [102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
            "Volume": [1000, 1000, 1000, 1000, 1000, 1000],
        },
        index=pd.date_range("2024-01-01", periods=6),
    )

    rules = {
        "version": 1,
        "entry": {
            "conditions": [
                {
                    "indicator": "sma",
                    "params": {"period": 2},
                    "operator": "gt",
                    "against": 0.0,
                }
            ],
            "logic": "AND",
        },
        "exit": {
            "conditions": [
                {
                    "indicator": "rsi",
                    "params": {"period": 2},
                    "operator": "lt",
                    "against": 100.0,
                }
            ]
        },
        "position_sizing": {"type": "fixed_fraction", "value": 0.5},
    }

    interpreter = StrategyInterpreter()
    StrategyClass = interpreter.interpret(rules)

    # Need to bypass warmup block for testing
    OriginalNext = StrategyClass.next

    def next_with_warmup(self):
        OriginalNext(self)

    StrategyClass.next = next_with_warmup

    bt = Backtest(data, StrategyClass, cash=10000, trade_on_close=False)

    # We just want to see it runs without errors and produces a result
    result = bt.run()
    assert "Return [%]" in result


def test_interpreter_generates_trades():
    # Regression guard for the "every backtest completes with 0 trades" bug: indicators were stored
    # in a dict, so backtesting.py never sliced them per bar and no signal ever fired. A crossover
    # over an oscillating series MUST produce trades once the indicators are sliced correctly.
    data = _synthetic_ohlcv()
    StrategyClass = StrategyInterpreter().interpret(_SMA_CROSS_RULES)

    result = Backtest(
        data,
        StrategyClass,
        cash=10000,
        commission=0.001,
        spread=0.0,
        margin=1.0,
        trade_on_close=False,
        exclusive_orders=True,
        finalize_trades=True,
    ).run()

    assert len(result._trades) > 0


def test_indicators_sliced_per_bar():
    # Pin the root cause directly: interpreted indicators must be discoverable by backtesting.py
    # (i.e. live in strategy.__dict__ as _Indicator values), and their per-bar value must actually
    # change across the run rather than being frozen at the final bar's value.
    data = _synthetic_ohlcv()
    StrategyClass = StrategyInterpreter().interpret(_SMA_CROSS_RULES)

    seen: list[float] = []
    original_next = StrategyClass.next

    def capturing_next(self):
        assert _strategy_indicators(self), "no indicators registered as sliceable strategy attributes"
        seen.append(float(self.sma_period5[-1]))
        original_next(self)

    StrategyClass.next = capturing_next
    Backtest(data, StrategyClass, cash=10000, trade_on_close=False).run()

    assert len(set(seen)) > 1, "indicator value is frozen across bars (not sliced per bar)"
