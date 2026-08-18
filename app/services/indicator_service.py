"""Indicator service — coordinates data fetching and pure domain calculations."""

import datetime

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.indicators import INDICATOR_MAP
from app.repositories.market_data_repo import MarketDataRepository


class IndicatorService:
    def __init__(self, session: AsyncSession):
        self.repo = MarketDataRepository(session)

    def _get_lookback_days(self, indicator: str, params: dict) -> int:
        """Determine required historical data (warm-up) for an indicator."""
        if indicator == "sma":
            return params.get("period", 20)
        elif indicator == "ema":
            return 2 * params.get("period", 20)
        elif indicator == "rsi":
            return 2 * params.get("period", 14)
        elif indicator == "macd":
            return 2 * (params.get("slow", 26) + params.get("signal", 9))
        elif indicator == "bollinger":
            return params.get("period", 20)
        elif indicator == "atr":
            return 2 * params.get("period", 14)
        else:
            raise ValidationError(f"Unknown indicator: {indicator}")

    def _validate_params(self, indicator: str, params: dict) -> None:
        """Validate indicator-specific parameters."""
        if indicator in ("sma", "ema", "rsi", "bollinger", "atr"):
            period = params.get("period")
            if period is not None and period <= 0:
                raise ValidationError("Period must be > 0")
        elif indicator == "macd":
            fast = params.get("fast", 12)
            slow = params.get("slow", 26)
            signal = params.get("signal", 9)
            if fast <= 0 or slow <= 0 or signal <= 0:
                raise ValidationError("MACD periods must be > 0")
            if fast >= slow:
                raise ValidationError("MACD fast period must be < slow period")

    async def calculate(
        self,
        symbol: str,
        indicator: str,
        params: dict,
        start: datetime.date,
        end: datetime.date,
    ) -> tuple[list[datetime.date], list[float] | list[dict[str, float]]]:
        """Calculate indicator values for a date range.

        Handles warm-up data transparently.

        Returns:
            Tuple of (dates, values). For multi-value indicators (MACD, Bollinger),
            values is a list of dicts.
        """
        indicator = indicator.lower()
        if indicator not in INDICATOR_MAP:
            raise ValidationError(f"Unknown indicator: {indicator}")

        self._validate_params(indicator, params)

        symbol = symbol.upper()
        ticker = await self.repo.get_ticker_by_symbol(symbol)
        if not ticker:
            raise NotFoundError(f"Ticker {symbol} not found.")

        lookback_days = self._get_lookback_days(indicator, params)
        # Approximate calendar days to trading days (add weekends/holidays buffer)
        calendar_buffer = int(lookback_days * 1.5) + 5
        lookback_date = start - datetime.timedelta(days=calendar_buffer)

        # Fetch data including warm-up period
        ohlcv_records = await self.repo.get_ohlcv(ticker.id, lookback_date, end)

        if not ohlcv_records:
            raise ValidationError(f"No data available for {symbol}")

        # Convert to DataFrame
        df = pd.DataFrame(
            [
                {
                    "date": r.date,
                    "open": float(r.open),
                    "high": float(r.high),
                    "low": float(r.low),
                    "close": float(r.close),
                    "volume": r.volume,
                }
                for r in ohlcv_records
            ]
        )
        df = df.set_index("date").sort_index()

        # Check if we have enough warm-up rows BEFORE the requested start date
        warmup_rows = df[df.index < start]
        if len(warmup_rows) < lookback_days:
            raise ValidationError(
                f"Insufficient historical data for {indicator} warm-up. "
                f"Required {lookback_days} trading days prior to {start}, "
                f"but found {len(warmup_rows)}."
            )

        # Dispatch to pure domain calculator
        calculator = INDICATOR_MAP[indicator]
        result = calculator.calculate(df, **params)

        # Trim result to requested date range
        if isinstance(result, pd.Series):
            trimmed = result.loc[start:end]
            # Drop NaN values that might still exist if lookback was
            # somehow insufficient
            # (though our check above should prevent this)
            trimmed = trimmed.dropna()
            dates = trimmed.index.tolist()
            values = trimmed.tolist()
        elif isinstance(result, pd.DataFrame):
            trimmed = result.loc[start:end].dropna()
            dates = trimmed.index.tolist()
            values = trimmed.to_dict("records")
        else:
            raise TypeError("Calculator returned unexpected type")

        return dates, values
