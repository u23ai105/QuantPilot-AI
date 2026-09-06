import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.health import router as health_router
from app.api.middleware import MetricsMiddleware, RateLimitMiddleware
from app.api.v1.router import api_router
from app.core.cache import close_cache
from app.core.config import settings
from app.core.exceptions import (
    QuantPilotException,
    global_exception_handler,
    quantpilot_exception_handler,
)
from app.core.logging import setup_logging
from app.core.rate_limit import RateLimiter

setup_logging()
logger = structlog.get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def create_app() -> FastAPI:
    limiter = RateLimiter(settings.redis_url) if settings.rate_limit_enabled else None

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        if limiter is not None:
            await limiter.close()
        # The query-embedding cache holds a lazily created connection pool; nothing to close if no
        # retrieval request ever ran.
        await close_cache()

    app = FastAPI(title=settings.app_name, version="0.1.0", description="QuantPilot AI API", lifespan=lifespan)

    # Added first, so it ends up *innermost*: Starlette builds the stack so the last-added middleware
    # is outermost. A 429 raised outside CORSMiddleware would carry no `Access-Control-Allow-Origin`,
    # and the browser would surface it as an opaque network error instead of a readable 429.
    if limiter is not None:
        app.add_middleware(RateLimitMiddleware, limiter=limiter)

    cors_origins = settings.cors_origins
    if isinstance(cors_origins, str):
        allow_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
    else:
        allow_origins = cors_origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Only a short safelist of response headers is readable from JS cross-origin, and the SPA is
        # served from a different origin than the API. Without this the browser silently hides the
        # rate-limit budget and the request id from `fetch`.
        expose_headers=["X-Request-ID", "Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    )

    app.add_middleware(RequestIdMiddleware)

    # Added last, so it is outermost: the timing then covers the entire stack, and a 429 from the rate
    # limiter or an exception escaping the handlers is still counted.
    app.add_middleware(MetricsMiddleware)

    app.add_exception_handler(QuantPilotException, quantpilot_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    app.include_router(health_router)
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
