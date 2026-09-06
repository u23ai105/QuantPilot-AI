"""Prometheus metrics: definitions and the exposition payload.

Hand-rolled rather than an auto-instrumentation package for one reason: **label cardinality**. A
Prometheus time series is created per unique label combination and lives in memory forever, so
labelling by raw request path would mint a series for every backtest id, ticker symbol, and
404-probing scanner URL. Everything here labels by the *matched route template*
(`/api/v1/backtests/{backtest_id}`), and unmatched requests collapse into a single `<unmatched>`
bucket — see `route_label`.

Scope: a per-process registry. Each Uvicorn worker answers `/metrics` with its own numbers, which is
correct for counters and histograms (Prometheus sums across scrape targets) but means a single scrape
of a multi-worker deployment sees one worker's view. `prometheus_client` has a multiprocess mode for
that; it needs a shared `PROMETHEUS_MULTIPROC_DIR` and is only worth adding when the API actually runs
multiple workers behind one port.
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram
from prometheus_client.exposition import CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request

#: A dedicated registry instead of the default global one, so importing this module in a test does not
#: fight with metrics other libraries may have registered, and a registry can be built per test.
REGISTRY = CollectorRegistry()

#: Buckets in seconds. Skewed low because most endpoints are DB reads answering in tens of
#: milliseconds, with the long tail kept for yfinance ingestion and document uploads.
_LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)

http_requests_total = Counter(
    "quantpilot_http_requests_total",
    "HTTP requests by method, matched route template and status code.",
    ["method", "route", "status"],
    registry=REGISTRY,
)

http_request_duration_seconds = Histogram(
    "quantpilot_http_request_duration_seconds",
    "HTTP request latency in seconds, by method and matched route template.",
    ["method", "route"],
    buckets=_LATENCY_BUCKETS,
    registry=REGISTRY,
)

http_requests_exceptions_total = Counter(
    "quantpilot_http_requests_exceptions_total",
    "Requests whose handler raised instead of returning a response.",
    ["method", "route"],
    registry=REGISTRY,
)

rate_limit_rejections_total = Counter(
    "quantpilot_rate_limit_rejections_total",
    "Requests rejected with 429, by rate-limit rule name.",
    ["rule"],
    registry=REGISTRY,
)

backtest_submissions_total = Counter(
    "quantpilot_backtest_submissions_total",
    "Backtest submissions by outcome: a new queued run, or an Idempotency-Key replay that returned an existing one.",
    ["outcome"],
    registry=REGISTRY,
)

#: Label value for requests that matched no route. Without this collapse, every 404 from a scanner
#: probing `/wp-login.php`-style paths would add a permanent series. FastAPI's own docs routes
#: (`/docs`, `/openapi.json`) also land here — they are served without a `route` in the request scope —
#: which is harmless, since they are not part of the API surface being measured.
UNMATCHED_ROUTE = "<unmatched>"


def route_label(request: Request) -> str:
    """The matched route's full path template, or `UNMATCHED_ROUTE`.

    Starlette puts the matched `route` in the request scope during routing, and its `path` carries the
    parameter names intact (`/backtests/{backtest_id}`) — the bounded-cardinality label we want, never
    `request.url.path`, which carries ids.

    That template is relative to the router the route was included from, though, so it lacks the
    `/api/v1` mount prefix and would collide across routers. The prefix is recovered by aligning the
    template's segments to the *end* of the concrete path: everything before them is literal mount
    prefix. Substituting parameter values into the path directly would be the obvious alternative, but
    a value equal to a prefix segment (`/api/v1/market-data/api`) would rewrite the wrong one.
    """
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if not isinstance(template, str):
        return UNMATCHED_ROUTE

    template_segments = [segment for segment in template.split("/") if segment]
    path_segments = [segment for segment in request.scope.get("path", "").split("/") if segment]
    prefix = path_segments[: max(0, len(path_segments) - len(template_segments))]
    return "/" + "/".join([*prefix, *template_segments])


def render() -> tuple[bytes, str]:
    """The exposition-format payload and its content type, for the `/metrics` response."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
