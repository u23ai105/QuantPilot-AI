"""Rate-limiting middleware.

Route groups are limited separately because their costs differ by orders of magnitude: a chat turn
burns LLM quota, a backtest submission occupies a Celery worker, a login attempt is cheap but is the
one endpoint worth throttling against credential stuffing.
"""

from __future__ import annotations

import re

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.rate_limit import RateLimiter, RateLimitRule
from app.core.security import decode_token_subject

logger = structlog.get_logger(__name__)

#: `(method regex, path regex, rule)`, first match wins. Paths are matched against the full request
#: path, so they include the `/api/v1` prefix the router is mounted under.
DEFAULT_RULES: list[tuple[str, str, RateLimitRule]] = [
    # Chat spends Gemini quota, which is the scarcest resource here.
    (r"^POST$", r"^/api/v1/conversations/[^/]+/messages$", RateLimitRule("chat", limit=20, window_seconds=60)),
    # Each accepted backtest occupies a Celery worker for seconds to minutes.
    (r"^POST$", r"^/api/v1/backtests$", RateLimitRule("backtest", limit=10, window_seconds=60)),
    # Ingestion and uploads both call out to third parties (yfinance) or do heavy parsing.
    (r"^POST$", r"^/api/v1/market-data/[^/]+/ingest$", RateLimitRule("ingest", limit=10, window_seconds=60)),
    (r"^POST$", r"^/api/v1/documents$", RateLimitRule("upload", limit=10, window_seconds=60)),
    # Unauthenticated and therefore keyed by IP: throttle credential stuffing.
    (r"^POST$", r"^/api/v1/auth/(login|register)$", RateLimitRule("auth", limit=10, window_seconds=60)),
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Applies `DEFAULT_RULES` to matching requests and adds `X-RateLimit-*` headers.

    Identity is the authenticated user id when a valid bearer token is present, and the client IP
    otherwise. Using the user id matters for the authenticated groups: several users behind one NAT
    would otherwise share a single budget, and one user could exhaust it for everyone.
    """

    def __init__(self, app, limiter: RateLimiter, rules: list[tuple[str, str, RateLimitRule]] | None = None) -> None:
        super().__init__(app)
        self._limiter = limiter
        self._rules = [(re.compile(m), re.compile(p), rule) for m, p, rule in (rules if rules is not None else DEFAULT_RULES)]

    def _match(self, method: str, path: str) -> RateLimitRule | None:
        for method_re, path_re, rule in self._rules:
            if method_re.match(method) and path_re.match(path):
                return rule
        return None

    @staticmethod
    def _identity(request: Request) -> str:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            subject = decode_token_subject(auth[7:].strip())
            if subject:
                return f"user:{subject}"
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    async def dispatch(self, request: Request, call_next):
        rule = self._match(request.method, request.url.path)
        if rule is None:
            return await call_next(request)

        identity = self._identity(request)
        verdict = await self._limiter.check(rule, identity)

        if not verdict.allowed:
            logger.info("rate_limited", rule=rule.name, path=request.url.path)
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded: {rule.limit} requests per {rule.window_seconds}s. Retry in {verdict.reset_after}s.",
                    }
                },
                headers={
                    "Retry-After": str(verdict.reset_after),
                    "X-RateLimit-Limit": str(verdict.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(verdict.reset_after),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(verdict.limit)
        response.headers["X-RateLimit-Remaining"] = str(verdict.remaining)
        response.headers["X-RateLimit-Reset"] = str(verdict.reset_after)
        return response
