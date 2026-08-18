from unittest.mock import AsyncMock

import pytest

from app.domain.strategy_validator import StrategyValidator, ValidationError


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def validator(mock_session):
    v = StrategyValidator(mock_session)
    # Mock _get_valid_tickers to return a static set instead of hitting the DB
    v._get_valid_tickers = AsyncMock(return_value={"AAPL", "MSFT"})
    return v


@pytest.mark.asyncio
async def test_valid_strategy(validator):
    rules = {
        "version": 1,
        "entry": {
            "conditions": [
                {
                    "indicator": "sma",
                    "params": {"period": 10},
                    "operator": "crosses_above",
                    "against": {"indicator": "sma", "params": {"period": 30}},
                }
            ],
            "logic": "AND",
        },
        "exit": {
            "conditions": [
                {
                    "indicator": "rsi",
                    "params": {"period": 14},
                    "operator": "gt",
                    "against": 70.0,
                }
            ]
        },
        "position_sizing": {"type": "fixed_fraction", "value": 0.5},
    }

    # Should not raise
    await validator.validate(rules)


@pytest.mark.asyncio
async def test_invalid_indicator(validator):
    rules = {"version": 1, "entry": {"conditions": [{"indicator": "unknown_ind", "operator": "gt", "against": 0}]}, "exit": {"conditions": []}}

    with pytest.raises(ValidationError, match="not in the supported indicator registry"):
        await validator.validate(rules)


@pytest.mark.asyncio
async def test_invalid_ticker(validator):
    rules = {
        "version": 1,
        "entry": {"conditions": [{"indicator": "sma", "params": {"period": 10, "symbol": "INVALID"}, "operator": "gt", "against": 0}]},
        "exit": {"conditions": []},
    }

    with pytest.raises(ValidationError, match="not in the fixed ticker universe"):
        await validator.validate(rules)


@pytest.mark.asyncio
async def test_invalid_position_sizing(validator):
    rules = {"version": 1, "entry": {"conditions": []}, "exit": {"conditions": []}, "position_sizing": {"type": "fixed_fraction", "value": 1.5}}

    with pytest.raises(ValidationError, match="Position sizing value must be between"):
        await validator.validate(rules)
