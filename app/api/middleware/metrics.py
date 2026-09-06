"""Middleware that records request count, latency and handler exceptions.

Placement matters: this is added *last* in `create_app`, making it the outermost middleware, so the
timing covers the whole stack (including rate limiting and CORS) and a 429 or a handler exception is
still counted. The trade-off is that `route_label` needs the route Starlette resolves further in — it
reads it from the request scope *after* `call_next` returns, by which point routing has run and
populated it.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core import metrics

#: `/metrics` itself is excluded: scraping every 15s would otherwise dominate the request counters and
#: make the latency histogram describe the scrape rather than the API.
EXCLUDED_PATHS = frozenset({"/metrics"})


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # An exception here means no response was produced, so there is no status code to label.
            # Counted separately rather than as a synthetic 500 so the two stay distinguishable: the
            # registered exception handlers turn most failures into real 500 *responses*, and anything
            # landing in this counter escaped them.
            metrics.http_requests_exceptions_total.labels(method=request.method, route=metrics.route_label(request)).inc()
            metrics.http_request_duration_seconds.labels(method=request.method, route=metrics.route_label(request)).observe(
                time.perf_counter() - started
            )
            raise

        elapsed = time.perf_counter() - started
        route = metrics.route_label(request)
        metrics.http_requests_total.labels(method=request.method, route=route, status=str(response.status_code)).inc()
        metrics.http_request_duration_seconds.labels(method=request.method, route=route).observe(elapsed)
        return response
