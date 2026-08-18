import pandas as pd
from backtesting import Backtest

from app.domain.strategy_interpreter import StrategyInterpreter


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
