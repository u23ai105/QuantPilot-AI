"""Bollinger Bands calculator.

Convention: Middle = SMA(period). std uses ddof=1 (pandas default).
Upper = middle + std_dev * sigma. Lower = middle - std_dev * sigma.
"""

import pandas as pd


class BollingerCalculator:
    @staticmethod
    def calculate(
        data: pd.DataFrame,
        period: int = 20,
        std_dev: float = 2.0,
    ) -> pd.DataFrame:
        """Calculate Bollinger Bands.

        Args:
            data: OHLCV DataFrame with 'close' column.
            period: SMA/std rolling window.
            std_dev: Number of standard deviations.

        Returns:
            DataFrame with columns [middle, upper, lower].
        """
        sma = data["close"].rolling(window=period).mean()
        std = data["close"].rolling(window=period).std(ddof=1)
        return pd.DataFrame(
            {
                "middle": sma,
                "upper": sma + (std * std_dev),
                "lower": sma - (std * std_dev),
            }
        )
