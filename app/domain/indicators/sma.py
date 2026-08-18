"""Simple Moving Average calculator.

Convention: rolling(window=period, min_periods=period).mean()
"""

import pandas as pd


class SMACalculator:
    @staticmethod
    def calculate(data: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate SMA on close prices.

        Args:
            data: OHLCV DataFrame with 'close' column.
            period: Rolling window size.

        Returns:
            Series of SMA values. First (period-1) values are NaN.
        """
        return data["close"].rolling(window=period, min_periods=period).mean()
