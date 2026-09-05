"""Root conftest — runs before `tests/conftest.py` imports the app, so env defaults set here apply.

Rate limiting is disabled for the suite. `httpx`'s ASGI transport reports the same client address for
every request, so all unauthenticated tests share one bucket: a real per-minute budget would leak
across tests and make the result depend on collection order and on how fast the suite runs.
`tests/test_rate_limit.py` builds its own app with the middleware installed explicitly.
"""

import os

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
