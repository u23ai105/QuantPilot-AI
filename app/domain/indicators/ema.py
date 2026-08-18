"""Exponential Moving Average calculator.

Convention: ewm(span=period, adjust=False).mean()
"""

import pandas as pd


class EMACalculator:
    @staticmethod
    def calculate(data: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate EMA on close prices.

        Args:
            data: OHLCV DataFrame with 'close' column.
            period: EMA span.

        Returns:
            Series of EMA values.
        """
        return data["close"].ewm(span=period, adjust=False).mean()
