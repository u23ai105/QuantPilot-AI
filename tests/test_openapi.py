"""Guards on the generated OpenAPI schema.

The schema is the published API surface — `/docs` is how anyone first meets this API — so the parts of
it that go stale silently are asserted here rather than left to review. These tests read the schema, not
a response, so unlike the rest of the suite they need no Postgres.
"""

import re

from app.api.middleware.rate_limit import DEFAULT_RULES
from app.main import app

SPEC = app.openapi()
SSE_PATH = "/api/v1/conversations/{conversation_id}/messages"


def _operations():
    """Yield `(method, path, operation)` for every documented operation."""
    for path, operations in SPEC["paths"].items():
        for method, operation in operations.items():
            yield method.upper(), path, operation


def _as_concrete_path(template: str) -> str:
    """`/api/v1/backtests/{backtest_id}` → `/api/v1/backtests/x`, to match against the rate-limit regexes."""
    return re.sub(r"\{[^}]+\}", "x", template)


def test_every_operation_has_a_summary_and_description():
    """A route with neither reads as an unlabelled verb in `/docs`."""
    undocumented = [(method, path) for method, path, operation in _operations() if not operation.get("summary") or not operation.get("description")]
    assert undocumented == []


def test_rate_limited_endpoints_document_429():
    """Keeps the docs honest about the limiter: the rule table is the source of truth, not prose.

    Checked in both directions, because both failures mislead a client — a limited endpoint with no
    documented 429 leaves retry handling to be discovered the hard way, and a documented 429 on an
    unlimited endpoint invents a response that can never arrive.
    """
    undocumented, spurious = [], []
    for method, path, operation in _operations():
        concrete = _as_concrete_path(path)
        is_limited = any(re.match(method_re, method) and re.match(path_re, concrete) for method_re, path_re, _ in DEFAULT_RULES)
        documents_429 = "429" in operation.get("responses", {})
        if is_limited and not documents_429:
            undocumented.append((method, path))
        if documents_429 and not is_limited:
            spurious.append((method, path))
    assert undocumented == []
    assert spurious == []


def test_streaming_endpoint_is_documented_as_sse_only():
    """It returns `text/event-stream` and never JSON; the schema used to claim otherwise.

    FastAPI infers the content type from the response class, and `StreamingResponse.media_type` is
    `None` — hence the `SSEResponse` subclass in the router.
    """
    responses = SPEC["paths"][SSE_PATH]["post"]["responses"]
    assert list(responses["200"]["content"]) == ["text/event-stream"]


def test_streaming_endpoint_documents_its_failure_modes():
    """The ones a client cannot infer from the happy path: ownership, the limiter, and a missing API key."""
    responses = SPEC["paths"][SSE_PATH]["post"]["responses"]
    for code in ("403", "404", "429", "502"):
        assert code in responses, f"POST {SSE_PATH} should document {code}"
