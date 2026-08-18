from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.backtests import router as backtests_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.indicators import router as indicators_router
from app.api.v1.market_data import router as market_data_router
from app.api.v1.strategies import router as strategies_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(market_data_router, prefix="/market-data", tags=["market-data"])
api_router.include_router(indicators_router, prefix="/indicators", tags=["indicators"])
api_router.include_router(strategies_router)
api_router.include_router(backtests_router)
api_router.include_router(conversations_router)
