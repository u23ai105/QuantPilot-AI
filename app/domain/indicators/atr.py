"""Average True Range calculator.

Convention: True Range smoothed with Wilder's method
(EWM with com=period-1, min_periods=period, adjust=False).
"""

import pandas as pd


class ATRCalculator:
    @staticmethod
    def calculate(data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range.

        Args:
            data: OHLCV DataFrame with 'high', 'low', 'close' columns.
            period: ATR smoothing period.

        Returns:
            Series of ATR values.
        """
        high_low = data["high"] - data["low"]
        high_close = (data["high"] - data["close"].shift()).abs()
        low_close = (data["low"] - data["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.ewm(com=period - 1, min_periods=period, adjust=False).mean()
