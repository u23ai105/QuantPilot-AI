from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticker import Ticker


class ValidationError(Exception):
    pass


class StrategyValidator:
    SUPPORTED_INDICATORS = {"sma", "ema", "rsi", "macd", "bollinger", "atr"}
    SUPPORTED_OPERATORS = {
        "gt",
        "lt",
        "gte",
        "lte",
        "eq",
        "crosses_above",
        "crosses_below",
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_valid_tickers(self) -> set[str]:
        stmt = select(Ticker.symbol)
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def validate(self, rules_json: dict[str, Any]) -> None:
        """Validates strategy JSON against the supported schema and constraints."""
        valid_tickers = await self._get_valid_tickers()

        if "version" not in rules_json or rules_json["version"] != 1:
            raise ValidationError("Unsupported strategy version. Only version 1 is supported.")

        if "entry" not in rules_json or "exit" not in rules_json:
            raise ValidationError("Strategy must define 'entry' and 'exit' groups.")

        for group_name in ["entry", "exit"]:
            group = rules_json[group_name]
            if not isinstance(group, dict) or "conditions" not in group:
                raise ValidationError(f"Group '{group_name}' must contain 'conditions'.")

            for condition in group["conditions"]:
                await self._validate_condition(condition, valid_tickers)

        if "position_sizing" in rules_json:
            ps = rules_json["position_sizing"]
            if ps.get("type") != "fixed_fraction":
                raise ValidationError("Position sizing type must be 'fixed_fraction'.")
            value = ps.get("value")
            if not isinstance(value, (int, float)) or not (0 < value <= 1.0):
                raise ValidationError("Position sizing value must be between 0 and 1.0.")

    async def _validate_indicator_config(self, config: dict[str, Any], valid_tickers: set[str]) -> None:
        indicator = config.get("indicator")
        if indicator not in self.SUPPORTED_INDICATORS:
            raise ValidationError(
                f"Indicator '{indicator}' is not in the supported indicator registry. Supported: {', '.join(sorted(self.SUPPORTED_INDICATORS))}"
            )

        params = config.get("params", {})
        if not isinstance(params, dict):
            raise ValidationError("Params must be a dictionary.")

        # Period constraint
        if "period" in params:
            period = params["period"]
            if not isinstance(period, int) or period <= 0:
                raise ValidationError("Indicator 'period' must be a positive integer.")

        # Ticker constraint if referenced
        if "symbol" in params or "ticker" in params:
            symbol = params.get("symbol") or params.get("ticker")
            if symbol not in valid_tickers:
                raise ValidationError(f"Referenced symbol '{symbol}' is not in the fixed ticker universe.")

    async def _validate_condition(self, condition: dict[str, Any], valid_tickers: set[str]) -> None:
        # Validate primary indicator
        await self._validate_indicator_config(condition, valid_tickers)

        # Validate operator
        operator = condition.get("operator")
        if operator not in self.SUPPORTED_OPERATORS:
            raise ValidationError(f"Operator '{operator}' is not supported.")

        # Validate against
        against = condition.get("against")
        if isinstance(against, dict):
            await self._validate_indicator_config(against, valid_tickers)
        elif not isinstance(against, (int, float)):
            raise ValidationError("'against' must be a number or another indicator config.")
