from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IndicatorConfig(BaseModel):
    indicator: Literal["sma", "ema", "rsi", "macd", "bollinger", "atr"]
    params: dict[str, Any] = Field(default_factory=dict)


class StrategyCondition(BaseModel):
    indicator: Literal["sma", "ema", "rsi", "macd", "bollinger", "atr"]
    params: dict[str, Any] = Field(default_factory=dict)
    operator: Literal["gt", "lt", "gte", "lte", "eq", "crosses_above", "crosses_below"]
    against: IndicatorConfig | float | int


class StrategyLogicGroup(BaseModel):
    conditions: list[StrategyCondition]
    logic: Literal["AND", "OR"] = "AND"


class StrategyPositionSizing(BaseModel):
    type: Literal["fixed_fraction"]
    value: float = Field(gt=0, le=1.0)


class StrategyRules(BaseModel):
    version: int = 1
    entry: StrategyLogicGroup
    exit: StrategyLogicGroup
    position_sizing: StrategyPositionSizing


class StrategyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    rules_json: StrategyRules


class StrategyResponse(BaseModel):
    id: int
    user_id: UUID
    name: str
    rules_json: dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
