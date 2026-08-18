import pandas as pd
import pytest

from app.domain.indicators.atr import ATRCalculator
from app.domain.indicators.bollinger import BollingerCalculator
from app.domain.indicators.ema import EMACalculator
from app.domain.indicators.macd import MACDCalculator
from app.domain.indicators.rsi import RSICalculator
from app.domain.indicators.sma import SMACalculator


@pytest.fixture
def sample_data():
    """Create a deterministic synthetic OHLCV dataset for known-answer tests."""
    # Data length: 30 days
    dates = pd.date_range("2024-01-01", periods=30)
    # Simple linear trend with some volatility

    # We create a specific sequence to test calculations accurately
    closes = [
        100.0,
        101.0,
        102.0,
        101.5,
        100.5,
        99.0,
        98.0,
        97.5,
        98.5,
        100.0,
        102.0,
        104.0,
        105.0,
        106.0,
        105.5,
        104.0,
        102.0,
        101.0,
        101.5,
        103.0,
        105.0,
        107.0,
        109.0,
        110.0,
        108.0,
        106.0,
        105.0,
        104.0,
        105.0,
        107.0,
    ]

    data = []
    for i, close in enumerate(closes):
        # High is slightly above close/prev_close, low is slightly below
        prev_close = closes[max(0, i - 1)]
        high = max(close, prev_close) + 1.0
        low = min(close, prev_close) - 1.0
        # Open is midpoint of previous and current close
        open_price = (prev_close + close) / 2

        data.append(
            {
                "date": dates[i].date(),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000 + (i * 100),
            }
        )

    df = pd.DataFrame(data)
    df = df.set_index("date")
    return df


def test_sma_calculator(sample_data):
    # known answer for 5-day SMA at index 4 (100.0, 101.0, 102.0, 101.5, 100.5)
    # mean = 505.0 / 5 = 101.0
    period = 5
    result = SMACalculator.calculate(sample_data, period=period)

    # First 4 values should be NaN
    assert pd.isna(result.iloc[0 : period - 1]).all()
    # 5th value should be exact
    assert result.iloc[period - 1] == 101.0


def test_ema_calculator(sample_data):
    period = 5
    result = EMACalculator.calculate(sample_data, period=period)

    # EMA uses ewm(span=5, adjust=False)
    # pandas calculates first value as exactly the first close
    assert result.iloc[0] == 100.0

    # Second value = (Close - EMA_prev) * (2/(span+1)) + EMA_prev
    # alpha = 2 / (5+1) = 1/3
    # EMA_1 = (101.0 - 100.0) * (1/3) + 100.0 = 100.3333...
    assert pytest.approx(result.iloc[1], 0.0001) == 100.3333


def test_rsi_calculator(sample_data):
    period = 14
    result = RSICalculator.calculate(sample_data, period=period)

    # Ensure it calculates values.
    # First period-1 values should be NaN due to min_periods.
    assert pd.isna(result.iloc[0 : period - 1]).all()
    assert not pd.isna(result.iloc[period])
    # RSI must be 0-100
    assert (result.dropna() >= 0).all() and (result.dropna() <= 100).all()


def test_macd_calculator(sample_data):
    result = MACDCalculator.calculate(sample_data, fast=12, slow=26, signal=9)

    assert list(result.columns) == ["macd", "signal", "histogram"]
    assert not pd.isna(result["macd"].iloc[-1])
    assert not pd.isna(result["signal"].iloc[-1])
    assert not pd.isna(result["histogram"].iloc[-1])

    # macd = fast_ema - slow_ema
    fast_ema = sample_data["close"].ewm(span=12, adjust=False).mean()
    slow_ema = sample_data["close"].ewm(span=26, adjust=False).mean()
    expected_macd = fast_ema - slow_ema
    pd.testing.assert_series_equal(result["macd"], expected_macd, check_names=False)


def test_bollinger_calculator(sample_data):
    period = 20
    std_dev = 2.0
    result = BollingerCalculator.calculate(sample_data, period=period, std_dev=std_dev)

    assert list(result.columns) == ["middle", "upper", "lower"]

    # First 19 should be NaN
    assert pd.isna(result["middle"].iloc[0 : period - 1]).all()

    # Middle should exactly match SMA
    sma = SMACalculator.calculate(sample_data, period=period)
    pd.testing.assert_series_equal(result["middle"], sma, check_names=False)

    # Upper > Lower
    valid_result = result.dropna()
    assert (valid_result["upper"] > valid_result["lower"]).all()


def test_atr_calculator(sample_data):
    period = 14
    result = ATRCalculator.calculate(sample_data, period=period)

    # First 13 should be NaN
    assert pd.isna(result.iloc[0 : period - 1]).all()
    assert not pd.isna(result.iloc[-1])
