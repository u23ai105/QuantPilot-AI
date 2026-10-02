import hmac

import redis.asyncio as redis
from fastapi import APIRouter, Header, HTTPException, Response, status
from sqlalchemy import text

from app.core import metrics
from app.core.config import settings
from app.core.db import engine

router = APIRouter()


@router.get(
    "/health",
    summary="Liveness probe",
    description='Returns `{"status": "ok"}` if the process is up. Touches nothing external, so it stays 200 while '
    "Postgres or Redis is down — use `/ready` to decide whether to send traffic.",
)
async def health_check():
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Checks the dependencies the app cannot work without and reports each one: `SELECT 1` against Postgres "
    'and a `PING` against Redis, as `{"db": ..., "redis": ..., "status": ...}`.\n\n'
    'Note the status code is **200 either way** — a failed dependency shows up as `"db": "down"` with a '
    'top-level `"status": "error"`, not as a 503, so a probe must read the body rather than the code.',
)
async def readiness_check():
    status = {"db": "unknown", "redis": "unknown", "status": "ok"}
    is_ready = True

    # Check DB
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status["db"] = "ok"
    except Exception:
        status["db"] = "down"
        is_ready = False

    # Check Redis
    try:
        r = redis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        status["redis"] = "ok"
    except Exception:
        status["redis"] = "down"
        is_ready = False

    status["status"] = "ok" if is_ready else "error"
    return status


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Request counts, latency histograms, rate-limit rejections and backtest submission outcomes in Prometheus "
    "exposition format. Lives at the server root, outside `/api/v1`, because scrapers expect `/metrics`.\n\n"
    "Unauthenticated by default. Set `METRICS_TOKEN` to require `Authorization: Bearer <token>` — do that whenever the "
    "port is reachable from outside the deployment's private network, since the route names and traffic shape it exposes "
    "are operational detail.",
    responses={
        200: {"content": {"text/plain": {}}, "description": "Exposition-format metrics"},
        401: {"description": "`METRICS_TOKEN` is configured and the bearer token was missing or wrong"},
    },
    include_in_schema=False,
)
async def prometheus_metrics(authorization: str | None = Header(None)):
    if settings.metrics_token:
        supplied = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else ""
        # compare_digest, not `==`: a plain comparison short-circuits on the first differing byte, so
        # its timing leaks how much of the token a caller has right.
        if not hmac.compare_digest(supplied, settings.metrics_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid metrics token")

    payload, content_type = metrics.render()
    return Response(content=payload, media_type=content_type)
