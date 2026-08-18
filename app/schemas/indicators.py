import datetime

from pydantic import BaseModel


class IndicatorPointResponse(BaseModel):
    date: datetime.date
    value: float


class IndicatorMultiPointResponse(BaseModel):
    date: datetime.date
    values: dict[str, float]


class IndicatorResponse(BaseModel):
    symbol: str
    indicator: str
    points: list[IndicatorPointResponse]


class IndicatorMultiResponse(BaseModel):
    symbol: str
    indicator: str
    points: list[IndicatorMultiPointResponse]
