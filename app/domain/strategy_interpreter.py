import logging
from typing import Any, Callable

import pandas as pd
from backtesting import Strategy as BaseStrategy

from app.domain.indicators import INDICATOR_MAP

logger = logging.getLogger(__name__)


def indicator_wrapper(indicator_name: str, component: str | None = None) -> Callable:
    """Creates a function that backtesting.py's I() can use, returning a numpy array."""

    def func(df_wrapper, **params):
        df = df_wrapper
        if isinstance(df, pd.DataFrame):
            # Normalize column names to lowercase for Phase 2 indicator calculators
            df = df.rename(columns=str.lower)
        calculator = INDICATOR_MAP[indicator_name]
        result = calculator.calculate(df, **params)

        if component:
            return result[component].to_numpy()
        if isinstance(result, pd.DataFrame):
            # Default to first column if no component specified for multi-column indicator
            return result.iloc[:, 0].to_numpy()
        return result.to_numpy()

    # backtesting.py uses __name__ for caching/plotting
    suffix = f"_{component}" if component else ""
    func.__name__ = f"{indicator_name}{suffix}"
    return func


class StrategyInterpreter:
    def interpret(self, rules_json: dict[str, Any]) -> type[BaseStrategy]:
        """Translates JSON strategy rules into a backtesting.py Strategy subclass."""
        # rules_json is already validated by StrategyValidator

        class DynamicStrategy(BaseStrategy):
            def init(self):
                self._indicator_keys: set[str] = set()

                # Setup indicators for entry conditions
                self._setup_group(rules_json["entry"])
                # Setup indicators for exit conditions
                self._setup_group(rules_json["exit"])

            def _setup_group(self, group: dict[str, Any]):
                for condition in group["conditions"]:
                    self._setup_indicator(condition)
                    against = condition.get("against")
                    if isinstance(against, dict):
                        self._setup_indicator(against)

            def _setup_indicator(self, config: dict[str, Any]):
                ind_name = config["indicator"]
                params = config.get("params", {})

                # Generate a unique key for the indicator based on its params
                param_str = "_".join(f"{k}{v}" for k, v in sorted(params.items()))
                key = f"{ind_name}_{param_str}"

                if key in self._indicator_keys:
                    return
                self._indicator_keys.add(key)

                # Indicators MUST be stored as strategy attributes (not in a dict). backtesting.py only
                # slices to the current bar the _Indicator values it finds directly in strategy.__dict__
                # (see backtesting._util._strategy_indicators). Values hidden inside a dict stay
                # full-length for the whole run, so indicator[-1] would return the final bar's value on
                # every bar -> entry/exit conditions are constant -> no signal ever fires -> 0 trades.
                if ind_name == "bollinger":
                    for comp in ("upper", "lower", "middle"):
                        setattr(self, f"{key}_{comp}", self.I(indicator_wrapper(ind_name, comp), self.data.df, **params))
                elif ind_name == "macd":
                    for comp in ("macd", "signal", "histogram"):
                        setattr(self, f"{key}_{comp}", self.I(indicator_wrapper(ind_name, comp), self.data.df, **params))
                else:
                    setattr(self, key, self.I(indicator_wrapper(ind_name), self.data.df, **params))

            def _get_indicator_value(self, config: dict[str, Any], step: int = -1) -> float:
                ind_name = config["indicator"]
                params = config.get("params", {})
                param_str = "_".join(f"{k}{v}" for k, v in sorted(params.items()))
                key = f"{ind_name}_{param_str}"

                component = config.get("component")
                if ind_name in ["bollinger", "macd"]:
                    if not component:
                        component = "middle" if ind_name == "bollinger" else "macd"
                    key = f"{key}_{component}"

                return getattr(self, key)[step]

            def _evaluate_condition(self, condition: dict[str, Any]) -> bool:
                val1 = self._get_indicator_value(condition)

                against = condition["against"]
                if isinstance(against, dict):
                    val2 = self._get_indicator_value(against)
                else:
                    val2 = float(against)

                op = condition["operator"]
                if op == "gt":
                    return val1 > val2
                if op == "lt":
                    return val1 < val2
                if op == "gte":
                    return val1 >= val2
                if op == "lte":
                    return val1 <= val2
                if op == "eq":
                    return val1 == val2

                if op in ["crosses_above", "crosses_below"]:
                    val1_prev = self._get_indicator_value(condition, step=-2)
                    if isinstance(against, dict):
                        val2_prev = self._get_indicator_value(against, step=-2)
                    else:
                        val2_prev = float(against)

                    if op == "crosses_above":
                        return val1_prev <= val2_prev and val1 > val2
                    if op == "crosses_below":
                        return val1_prev >= val2_prev and val1 < val2

                return False

            def _evaluate_group(self, group: dict[str, Any]) -> bool:
                conditions = group["conditions"]
                logic = group.get("logic", "AND")

                results = [self._evaluate_condition(c) for c in conditions]

                if logic == "AND":
                    return all(results)
                elif logic == "OR":
                    return any(results)
                return False

            def next(self):
                # trade_on_close = False (configured outside in Backtest instantiation)
                # Next is called at the end of the bar t.
                # Actions here will be executed on bar t+1 open.
                entry_signal = self._evaluate_group(rules_json["entry"])
                exit_signal = self._evaluate_group(rules_json["exit"])

                if self.position:
                    if exit_signal:
                        self.position.close()
                else:
                    if entry_signal:
                        ps = rules_json.get("position_sizing", {})
                        if ps.get("type") == "fixed_fraction":
                            fraction = ps.get("value", 1.0)
                            self.buy(size=fraction)

        return DynamicStrategy
