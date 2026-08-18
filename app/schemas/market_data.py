import datetime

from pydantic import BaseModel, ConfigDict, Field


class TickerResponse(BaseModel):
    symbol: str = Field(..., description="Ticker symbol")
    name: str = Field(..., description="Company name")
    sector: str | None = Field(None, description="Sector")

    model_config = ConfigDict(from_attributes=True)


class OHLCVBarResponse(BaseModel):
    date: datetime.date
    open: float
    high: float
    low: float
    close: float
    volume: int

    model_config = ConfigDict(from_attributes=True)


class MarketDataResponse(BaseModel):
    symbol: str
    count: int
    bars: list[OHLCVBarResponse]
