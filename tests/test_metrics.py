"""`GET /metrics` and the instrumentation feeding it.

The behaviours worth pinning are the ones that go wrong quietly. Label cardinality is the main one: a
counter labelled with raw request paths grows a permanent time series per backtest id and per
404-probing scanner URL, and nothing about the endpoint *looks* broken while that happens. So the
route-template labelling and the `<unmatched>` collapse are asserted directly, not just "the endpoint
returns 200".
"""

import pytest
from httpx import ASGITransport, AsyncClient
from prometheus_client import CollectorRegistry, Counter
from prometheus_client.exposition import generate_latest

from app.api import health
from app.core import metrics


def _samples(name: str, payload: str) -> dict[tuple[tuple[str, str], ...], float]:
    """Parse exposition text into `{sorted label pairs: value}` for one metric name.

    Hand-parsed rather than read off the registry: this asserts on what a scraper actually receives,
    including the `_total` suffix the client library appends to counters.
    """
    found = {}
    for line in payload.splitlines():
        if line.startswith("#") or not line.startswith(name):
            continue
        head, _, value = line.rpartition(" ")
        if "{" in head:
            labels_str = head[head.index("{") + 1 : head.rindex("}")]
            pairs = tuple(sorted((p.split("=", 1)[0], p.split("=", 1)[1].strip('"')) for p in labels_str.split(",") if p))
        else:
            pairs = ()
        found[pairs] = float(value)
    return found


async def test_metrics_endpoint_serves_prometheus_exposition_format(client: AsyncClient):
    response = await client.get("/metrics")

    assert response.status_code == 200
    # Scrapers dispatch on this; a JSON content type would make the endpoint useless to Prometheus.
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "# TYPE quantpilot_http_requests_total counter" in body
    assert "# TYPE quantpilot_http_request_duration_seconds histogram" in body


async def test_requests_are_counted_by_route_template_not_by_path(client: AsyncClient, test_user_token: str):
    """The label must be `/backtests/{backtest_id}`, or every id ever requested becomes a time series."""
    headers = {"Authorization": f"Bearer {test_user_token}"}
    for backtest_id in (12345, 67890):
        await client.get(f"/api/v1/backtests/{backtest_id}", headers=headers)

    body = (await client.get("/metrics")).text
    counted = _samples("quantpilot_http_requests_total", body)

    template = {"method": "GET", "route": "/api/v1/backtests/{backtest_id}", "status": "404"}
    key = tuple(sorted(template.items()))
    assert key in counted, f"no series for the route template; got {list(counted)}"
    # Both ids collapsed onto the one series rather than creating two.
    assert counted[key] >= 2
    assert not [labels for labels in counted if any("12345" in value for _, value in labels)]


async def test_route_label_recovers_the_mount_prefix(client: AsyncClient, test_user_token: str):
    """Route templates are relative to their router, so the `/api/v1` prefix has to be reattached.

    Without it, two routers mounted at different prefixes with the same relative path would share one
    series, and the label would not identify a real URL.
    """
    headers = {"Authorization": f"Bearer {test_user_token}"}
    await client.get("/api/v1/backtests", headers=headers)

    body = (await client.get("/metrics")).text
    routes = {dict(labels).get("route") for labels in _samples("quantpilot_http_requests_total", body)}

    assert "/api/v1/backtests" in routes
    assert "/backtests" not in routes


async def test_unmatched_paths_collapse_into_a_single_series(client: AsyncClient):
    """A scanner walking made-up URLs must not be able to grow the registry."""
    for path in ("/wp-login.php", "/.env", "/admin/config"):
        await client.get(path)

    body = (await client.get("/metrics")).text
    counted = _samples("quantpilot_http_requests_total", body)

    unmatched = [labels for labels in counted if dict(labels).get("route") == metrics.UNMATCHED_ROUTE]
    assert len(unmatched) == 1
    assert counted[unmatched[0]] >= 3


async def test_latency_histogram_observes_the_request(client: AsyncClient):
    await client.get("/health")

    body = (await client.get("/metrics")).text
    counted = _samples("quantpilot_http_request_duration_seconds_count", body)

    key = tuple(sorted({"method": "GET", "route": "/health"}.items()))
    assert counted.get(key, 0) >= 1


async def test_metrics_endpoint_excludes_itself(client: AsyncClient):
    """Scraping every 15s would otherwise dominate the counters and skew the latency histogram."""
    await client.get("/metrics")
    body = (await client.get("/metrics")).text

    counted = _samples("quantpilot_http_requests_total", body)
    assert not [labels for labels in counted if dict(labels).get("route") == "/metrics"]


async def test_route_label_is_bounded_by_the_template(client: AsyncClient, test_user_token: str):
    """Ten distinct ids, one route label — the property that keeps the registry from growing with traffic.

    Asserted on the distinct *route* values rather than on the series count: the registry is
    process-wide, so other tests contribute their own status codes to the same route.
    """
    headers = {"Authorization": f"Bearer {test_user_token}"}
    for backtest_id in range(9000, 9010):
        await client.get(f"/api/v1/backtests/{backtest_id}", headers=headers)

    body = (await client.get("/metrics")).text
    routes = {dict(labels).get("route") for labels in _samples("quantpilot_http_requests_total", body)}

    assert "/api/v1/backtests/{backtest_id}" in routes
    assert not [route for route in routes if route and any(str(i) in route for i in range(9000, 9010))]


# ── Token gating ──────────────────────────────────────────────────────────────


@pytest.fixture
async def token_protected_client(monkeypatch):
    """A client against an app where `metrics_token` is set.

    `settings` is read inside the handler, so patching the attribute is enough — no app rebuild needed.
    """
    monkeypatch.setattr(health.settings, "metrics_token", "s3cret")
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client


async def test_token_gate_rejects_a_missing_or_wrong_token(token_protected_client: AsyncClient):
    assert (await token_protected_client.get("/metrics")).status_code == 401
    assert (await token_protected_client.get("/metrics", headers={"Authorization": "Bearer wrong"})).status_code == 401
    # A non-bearer scheme is not a partial credential either.
    assert (await token_protected_client.get("/metrics", headers={"Authorization": "Basic s3cret"})).status_code == 401


async def test_token_gate_accepts_the_configured_token(token_protected_client: AsyncClient):
    response = await token_protected_client.get("/metrics", headers={"Authorization": "Bearer s3cret"})

    assert response.status_code == 200
    assert "quantpilot_http_requests_total" in response.text


async def test_metrics_are_open_when_no_token_is_configured(client: AsyncClient):
    """Default posture: open, for a scraper on a private network. Documented on the route."""
    assert health.settings.metrics_token == ""
    assert (await client.get("/metrics")).status_code == 200


# ── Counter definitions ───────────────────────────────────────────────────────


def test_backtest_submission_outcomes_are_labelled_queued_and_replayed():
    """`backtest_service` increments these two label values; a rename here silently zeroes a dashboard."""
    payload = generate_latest(metrics.REGISTRY).decode()
    assert "quantpilot_backtest_submissions_total" in payload

    probe = CollectorRegistry()
    counter = Counter("probe_total", "probe", ["outcome"], registry=probe)
    counter.labels(outcome="queued").inc()
    counter.labels(outcome="replayed").inc()
    outcomes = {dict(labels)["outcome"] for labels in _samples("probe_total", generate_latest(probe).decode())}
    assert outcomes == {"queued", "replayed"}


def test_route_label_falls_back_when_no_route_is_in_scope():
    """Exception paths can reach the label helper before routing resolved anything."""

    class _ScopeOnly:
        scope: dict = {}

    assert metrics.route_label(_ScopeOnly()) == metrics.UNMATCHED_ROUTE
