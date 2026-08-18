"""MACD calculator.

Convention: Fast EMA(12), Slow EMA(26), Signal EMA(9).
All EMA use adjust=False.
Returns DataFrame with columns: macd, signal, histogram.
"""

import pandas as pd


class MACDCalculator:
    @staticmethod
    def calculate(
        data: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> pd.DataFrame:
        """Calculate MACD line, signal line, and histogram.

        Args:
            data: OHLCV DataFrame with 'close' column.
            fast: Fast EMA period.
            slow: Slow EMA period.
            signal: Signal EMA period.

        Returns:
            DataFrame with columns [macd, signal, histogram].
        """
        ema_fast = data["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = data["close"].ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return pd.DataFrame(
            {
                "macd": macd_line,
                "signal": signal_line,
                "histogram": histogram,
            }
        )
