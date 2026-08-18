from app.domain.indicators.atr import ATRCalculator
from app.domain.indicators.bollinger import BollingerCalculator
from app.domain.indicators.ema import EMACalculator
from app.domain.indicators.macd import MACDCalculator
from app.domain.indicators.rsi import RSICalculator
from app.domain.indicators.sma import SMACalculator

INDICATOR_MAP = {
    "sma": SMACalculator,
    "ema": EMACalculator,
    "rsi": RSICalculator,
    "macd": MACDCalculator,
    "bollinger": BollingerCalculator,
    "atr": ATRCalculator,
}

__all__ = [
    "ATRCalculator",
    "BollingerCalculator",
    "EMACalculator",
    "INDICATOR_MAP",
    "MACDCalculator",
    "RSICalculator",
    "SMACalculator",
]
