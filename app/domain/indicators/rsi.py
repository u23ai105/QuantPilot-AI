"""Relative Strength Index calculator.

Convention: Wilder's smoothing via ewm(com=period-1, min_periods=period,
adjust=False). This produces the classic Wilder RSI used by most charting
platforms.
"""

import pandas as pd


class RSICalculator:
    @staticmethod
    def calculate(data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Wilder's RSI on close prices.

        Args:
            data: OHLCV DataFrame with 'close' column.
            period: RSI lookback period.

        Returns:
            Series of RSI values (0-100 scale).
        """
        delta = data["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=period - 1, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
