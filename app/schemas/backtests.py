from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BacktestCreate(BaseModel):
    strategy_id: int
    symbol: str
    start_date: date
    end_date: date
    initial_capital: float = Field(10000.0, gt=0)
    commission: float = Field(0.001, ge=0)
    slippage: float = Field(0.000, ge=0)


class BacktestResponse(BaseModel):
    id: int
    strategy_id: int
    ticker_id: int
    start_date: date
    end_date: date
    initial_capital: float
    commission: float
    slippage: float
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BacktestResultResponse(BaseModel):
    id: int
    backtest_id: int
    total_return: float
    cagr: float
    volatility: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown: float
    win_rate: float | None
    total_trades: int
    equity_curve: list[dict[str, Any]] = Field(validation_alias="equity_curve_json")
    trades: list[dict[str, Any]] = Field(validation_alias="trades_json")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
