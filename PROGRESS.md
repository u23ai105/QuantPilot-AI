# Autonomous run progress

Test command used for every task: full `pytest` suite via the preview channel (the Bash sandbox
cannot reach Postgres, so DB-backed tests only run there). Baseline at start of run: **63 passed**.

## Final summary

**Tasks 0–20: all 21 done. Nothing blocked, nothing reverted, nothing abandoned.** The code landed in
16 commits, `ea1fe0e`..`6cb5df1` — 15 numbered-task commits plus one unnumbered UI fix (`81537a6`, the
broken Market Data page) — with this summary as the closing commit. Task 0 was environment bring-up and
produced no code. Three tasks were grouped where the work was one change: `2-4`, `7,9,12`, `19,20`.

The suite went from **63 passed to 126 passed** on the last full DB-backed run (coverage **68%**), and
the growth is the point: nearly every task added tests that would catch its own regression rather than
just making the change. Tasks 18–19 added 5 more, so **131** is now collected — those 5 need no
database and pass in the sandbox, but a full 131-test run has not been observed (see Blocked).

What each task left behind, in one line each:

| # | Change | Evidence it works |
| :-- | :-- | :-- |
| 0 | Environment brought up | 13 tables, alembic at head, `/ready` all-ok |
| 1 | HNSW index recreated in the migration instead of dropped | `pg_indexes` showed the index live after `upgrade head` |
| 2 | `SystemMessage` in the eval harness | code committed; **run deferred, needs quota** |
| 3 | Backtest ownership scoping | 6 tests: cross-user **404** on both read endpoints, list scoped |
| 4 | OAuth2 `tokenUrl` corrected | literal `/api/v1/auth/login`; the env name no longer leaks into it |
| 5 | README rewritten to match shipped code | three verified staleness bugs (phase, model ids, "Planned") |
| 6 | Vite template scaffolding deleted | unreferenced first, then `tsc -b` + `npm run build` clean, `/login` renders |
| 7, 9, 12 | Deps reconciled, `backtesting` upper-bounded, `pytest-cov` added | coverage report produced |
| 8 | `MemorySaver` removed; Postgres is the only conversation state | graph compiles with `checkpointer = None`, `/ready` all-ok, suite still green |
| 10 | Disabled UI elements wired up; tests stopped dropping the dev DB | each of the 5 items checked live, incl. the `/ready` degraded branch |
| 11 | Equity-curve chart on backtest rows | live run: 251 of 319 curve points plotted, chart lazy-loaded |
| 13 | Redis per-caller rate limiting | 429 + `Retry-After` tests, fail-open test |
| 14 | Idempotent backtest submission | replay returns the first run, 409 on key reuse |
| 15 | `/metrics` with bounded label cardinality | label-template tests, live scrape |
| 16 | Load test of the submission path | **measured**: 156.3 req/s, p95 0.214s, 200/200 → 202 |
| 17 | Redis cache for RAG query embeddings | "N queries → 1 embedding call" asserted; live Redis + dead-port check |
| 18 | OpenAPI docs on all 24 operations | 4 schema tests, incl. docs-vs-limiter cross-check |
| 19 | Flower + the task events it needs | both event flags asserted in `tests/test_worker.py` |
| 20 | Managed Postgres in `render.yaml` | fields verified against Render's blueprint spec |

Three things are **configured but never executed in this run**, and that distinction matters more than
the checkmarks above:

- The **eval harness** (task 2) — a deliberate choice, see the deferred section below.
- **Flower** (task 19) was never started: launching it needs either Docker (socket unreachable from the
  sandbox) or a `pip install flower` through the preview channel, which was down. The compose service,
  the dependency and the event flags are in place and the flags are unit-tested; the dashboard itself is
  unproven.
- The **Render blueprint** (task 20) was never synced — there is no deployment to sync it to. Every
  field name and semantic was checked against Render's published blueprint spec instead of assumed.

Known follow-ups, none of them blocking:

- `frontend/src/features/research/pages/ResearchPage.tsx` and `lib/api/resources.ts` inline the
  `VITE_API_BASE_URL` fallback instead of importing `API_BASE_URL` from `lib/api/client.ts`.
- No `LICENSE` file, and `pyproject.toml` declares no `license` field, though the README says MIT.
- `tsconfig*.json`, `.oxlintrc.json` and `components.json` are still swept up by the `*.json` line in
  `.gitignore` and exist only on disk — only `package.json`/`package-lock.json` are un-ignored.
- Frontend has no test suite at all; every UI task in this run was verified by hand in the browser.

## Task log

- **Task 0 — environment bring-up: done.** Verified live: 13 tables, alembic at head `c961f1f9fde9`,
  `/ready` returns `{"db":"ok","redis":"ok","status":"ok"}`. `greenlet` was NOT declared in
  pyproject.toml — added under task 7.
- **Task 1 — HNSW index migration: done.** Confirmed the defect live (`pg_indexes` showed no hnsw
  index on `document_chunks`, so every vector search was a seq scan). Root cause: the HNSW index is
  created with raw SQL in `f5da07b9db1a` (pgvector operator classes aren't expressible in the model),
  so autogenerate saw it as a stray index and emitted `drop_index` in `upgrade()` with the
  `create_index` inverted into `downgrade()`. Fixed: `upgrade()` now adds the column and re-creates
  the index idempotently (`CREATE INDEX IF NOT EXISTS`); `downgrade()` only reverses its own column.
  Verified by running `alembic downgrade -1 && alembic upgrade head`, then re-querying `pg_indexes`:
  `ix_document_chunks_embedding ... USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')`.
- **Task 2 — eval harness system prompt: done (not executed).** `scripts/run_eval.py` sent its
  instruction block as a `HumanMessage`, so the harness scored a different prompt structure than
  production, which sends it in the system role. Now a `SystemMessage` followed by the question as a
  `HumanMessage`. The harness itself was **not run** — it makes live Gemini calls (see Deferred).
- **Task 3 — backtest ownership check: done.** `GET /api/v1/backtests/{id}` and `/{id}/results` had no
  ownership check at all, and backtest ids are sequential ints, so any authenticated user could walk
  other users' runs and full result payloads. Scoped at the repository layer: `get_by_id` /
  `get_with_result` take an optional `user_id` and join `strategies` on `Strategy.user_id`; the service
  now requires it, and the router returns **404** (not 403) so ids stay unenumerable. Added
  `tests/test_backtests.py` with 6 tests: cross-user 404 on both read endpoints, owner still gets 200
  on both, list excludes other users' runs, list includes the owner's, list requires auth.
- **Task 4 — OAuth2 tokenUrl: done.** `app/api/deps.py` built the bearer scheme with
  `tokenUrl=f"{settings.app_env}/api/v1/auth/login"`, which put the environment name ("development")
  into the Swagger auth URL and broke the "Authorize" flow in `/docs`. Now the literal
  `"/api/v1/auth/login"`.

Suite after tasks 2–4: **69 passed** (63 baseline + 6 new).

- **Task 5 — README rewrite: done.** Three verified staleness bugs fixed: the badge and prose claimed
  "Phase 2 (Market Data & Indicators)" though `docs/phase-reports/` goes through Phase 7; the whole
  feature list was headed "Core Features (**Planned**)" while describing shipped code; and both model
  IDs were wrong — "Gemini 3.6 Flash" and "gemini-embedding-2" don't exist in the codebase, which uses
  `gemini-2.0-flash` (`app/core/config.py:20`) and `models/gemini-embedding-001`
  (`app/ai/embedding.py:17`). Also added an API-surface table generated from the actual `@router`
  decorators, the frontend setup and Celery queue commands, the non-hermetic-tests warning, and a
  deployment section from `render.yaml`. Removed the MIT badge and softened the license section: there
  is **no** committed `LICENSE` file and `pyproject.toml` declares no `license` field, so the old
  "See `LICENSE`" line pointed at nothing.
- **Task 6 — delete Vite scaffolding: done.** Removed `frontend/src/App.tsx`, `App.css`,
  `assets/react.svg`, `assets/vite.svg`. Confirmed unreferenced first: `main.tsx` mounts
  `RouterProvider` and imports only `index.css`, and a grep for those four paths outside `App.*` found
  nothing (`hero.png` is kept — it is the only asset still imported). Also fixed `frontend/index.html`,
  whose `<title>` was still the template default `frontend`; it now reads `QuantPilot AI`. Verified
  `npx tsc -b` clean, `npm run build` succeeds, and the running app renders `/login` with the new
  title (checked via the preview channel, no new console errors).
- **Task 7 — reconcile pyproject deps: done.** Audited every third-party import across
  `app/ scripts/ tests/ alembic/` against the manifest. Four real mismatches: `sse-starlette` was
  declared but **never imported** — the SSE endpoint is hand-rolled with `StreamingResponse`
  (`app/api/v1/conversations.py:91`) — so it was removed; `reportlab` is imported by
  `scripts/generate_benchmark_pdf.py:5` but was undeclared, now in the `dev` extra since it only builds
  eval fixtures; `langchain_core` is imported directly in 9 places but only arrived transitively, now
  declared; and `greenlet` is required by every async DB call yet SQLAlchemy only requires it
  conditionally (`platform_machine`/extras gated), so it is now declared directly. Verified by
  re-running `pip install -e ".[dev]"`: `Successfully installed coverage-7.16.0 pytest-cov-7.1.0
  reportlab-5.0.1`, exit 0, nothing uninstalled. Also wrote a checker that resolved every declared
  specifier against the installed version — all satisfied.
- **Task 9 — pin backtesting.py upper bound: done (folded into the task 7 commit).**
  `backtesting>=0.3.3` → `backtesting>=0.3.3,<0.7` (installed: 0.6.6). The interpreter depends on
  library internals — which `Strategy.__dict__` entries get sliced per bar (the root cause of the
  0-trades bug) and `finalize_trades` defaulting to False — so an unbounded major bump could silently
  break trade generation again.
- **Task 12 — pytest-cov: done.** Added `pytest-cov>=5.0.0` to the dev extra, plus
  `[tool.coverage.run]`/`[tool.coverage.report]` config (branch coverage, `source = ["app"]`,
  `show_missing`, `skip_covered`). CI now runs `pytest --cov --cov-report=term --cov-report=xml
  --cov-fail-under=63` and uploads `coverage.xml` as an artifact. Measured baseline from a real run:
  **65%** (2251 statements, 692 missed, 420 branches, 62 partial). The 63% floor is set just below the
  measured value so CI catches a genuine regression without tripping on noise.
- **Task 8 — remove MemorySaver: done.** The graph now compiles with no checkpointer. It wasn't merely
  redundant: `handle_message` already rebuilds the entire history from Postgres each turn, and
  `add_messages` merges by message id, so the DB-rebuilt messages (fresh ids every turn) made the
  checkpointed thread accumulate **another full copy of the conversation on every request** — unbounded,
  and invisible with more than one worker since `MemorySaver` is per-process. Also dropped the now
  meaningless `thread_id` from `config`, replacing it with tracing `metadata` (conversation + user id).
  Updated the three places that documented the old design: `AI_ARCHITECTURE.md` §6 (rewritten, with the
  `PostgresSaver` note now warning that a future checkpointer also requires switching to append-only
  turns), its §2.4 compile snippet, and `CLAUDE.md`. Verified: graph compiles with `checkpointer = None`,
  the reloaded API returns `/ready` = `{"db":"ok","redis":"ok","status":"ok"}`, suite still 69 passed.
- **Task 10 — disabled/dead UI elements: done.** Five items, each either wired to real data or removed
  when nothing backed it:
  - *Documents search input* — was `disabled`. Now a live client-side filename filter (the list
    endpoint has no search param and the whole list is already in memory), with a "No documents match
    …" empty state. Verified live against two seeded PROCESSED documents: `apple` → 1 card,
    `tesla` → empty state, cleared → both cards.
  - *⌘K button* — removed. There is no command-palette implementation, no `cmdk` dependency, and no
    keybinding, so the button could never do anything.
  - *"API: Connected" pill* — was hardcoded green text, i.e. it claimed health regardless of the
    backend. Now driven by `GET /ready` (30s poll, `retry: false`) with four states: Checking /
    Connected / Degraded (naming which of DB or Redis is down) / Unreachable, in a `role="status"
    aria-live="polite"` region. `/ready` is mounted at the app root, not under `/api/v1`, so
    `fetchClient` can't reach it — added `API_ROOT_URL` (derived from `API_BASE_URL` by stripping the
    version suffix) and a `healthApi.ready()` that fetches it directly. Both branches verified live:
    "API: Connected" against the real backend, "API: Degraded (Redis down)" against a patched `/ready`.
  - */settings sidebar link* — removed. No such route exists (React Router would render nothing) and
    there is no settings surface on the backend either.
  - *Backtest history* — `BacktestsPage` tracked run ids in `sessionStorage`, so history vanished on
    reload and was invisible to any other device. It now calls the real `GET /backtests` (already
    implemented and owner-scoped) via `backtestsApi.list()`, newest first, polling every 5s **only**
    while at least one run is not COMPLETED/FAILED. `StrategiesPage` correspondingly stopped writing
    `sessionStorage` and just invalidates the `["backtests"]` query. Verified live: 3 real rows
    rendered after a reload, with the RUNNING row polling.
- **Test harness — dev database was being destroyed (defect found during task 10, not a numbered
  task).** `tests/conftest.py` resolved its URL as `TEST_DATABASE_URL` → `DATABASE_URL` → settings, and
  `setup_test_db` runs `Base.metadata.drop_all` per test function — so with no `TEST_DATABASE_URL` set,
  every `pytest` run dropped all 13 tables of the **dev** database. That is what caused the
  `UndefinedTableError: relation "users" does not exist` seen mid-run. Fixed with
  `_default_test_database_url()`: reuse the configured connection details but suffix the database name
  with `_test` (idempotent if it already ends in `_test`, and any `?query` string is preserved).
  `TEST_DATABASE_URL` still wins when set. Proof: a full 69-passed run now leaves the dev DB with all
  13 tables, head revision, and the HNSW index intact.
- **Market Data page was fully broken (defect reported by the user mid-run, not a numbered task).**
  Every request the page made was rejected, so it showed "Failed to load market data", `$—` for close
  and volume, and two spinners that never resolved. Five distinct frontend/contract mismatches, all
  confirmed against the running API with the page's own token before fixing:
  - **No dates sent.** `getTickerData(activeSymbol)` passed no window, but `start`/`end` are required
    query params → `422 {"loc":["query","start"],"msg":"Field required"}`. That 422 was the red banner.
  - **Wrong param names.** `resources.ts` sent `start_date`/`end_date`; the router declares `start`/`end`
    (this was the mismatch already noted as out-of-scope earlier in the run). Same 422; with the correct
    names the same URL returns 251 bars.
  - **Indicators had the same missing-window bug**, so SMA/RSI 422'd too. With `retry: false` the query
    just left `data === undefined`, and the cards spun on `undefined` rather than on a real loading flag
    — a permanent spinner that read as a hang instead of an error.
  - **Response shapes were wrong.** Both endpoints return envelopes — `{"symbol","count","bars":[…]}`
    and `{"symbol","indicator","points":[…]}` — but the frontend typed them as bare arrays and did
    `ohlcv.length` / `ohlcv[ohlcv.length-1]`, which is `undefined` on an object. So even with the params
    fixed the table would still have said "No data available". `TickerResponse` was wrong too: it
    declared `id: number` and no `sector`, while the endpoint returns `{symbol, name, sector}`.
  - **Indicator warm-up.** Reusing the OHLCV window for indicators still 400s:
    `IndicatorService._get_lookback_days` requires `period` prior trading days for SMA and `2*period`
    for RSI, and asking from the earliest stored bar leaves zero rows ahead of it —
    `"Insufficient historical data for sma warm-up. Required 20 trading days prior to 2021-09-06, but
    found 0."` Fixed by starting the indicator window at the 41st stored bar (`INDICATOR_WARMUP_BARS = 40`,
    enough for RSI-14's 28) and gating the queries on `bars.length > 40`, so a thinly-ingested symbol
    shows a dash instead of a spinner that can never resolve.

  Verified live on `/market` after the fix: banner gone, `LATEST CLOSE $250.38 / 1.33%`,
  `VOLUME 35,557,500`, `SMA (20) 247.47`, `RSI (14) 60.23`, 10 table rows newest-first
  (2024-12-30 → 2024-12-16), zero spinners. Cross-checked those same numbers straight from the API:
  398 bars stored, indicator window 2023-07-31 → 2024-12-30, last SMA point 247.472095, last RSI
  60.22566910607216 — the UI is rendering real backend output, not a coincidence. Error path re-checked
  by searching `MSFT` (in the fixed universe but never ingested): banner returns, all four cards show
  `—`, the table reads "Could not load bars.", still zero spinners; searching `AAPL` again restores the
  data. `tsc -b` and `npm run build` clean, `npm run lint` reports nothing in the changed files.
- **Task 13 — Redis rate limiting: done.** There was no rate limiting anywhere before this (grep found
  only aspirational mentions in `docs/`), so chat, backtest submission, ingestion and login were all
  unbounded. Added `app/core/rate_limit.py` (fixed-window `RateLimiter` over Redis) and
  `app/api/middleware/rate_limit.py` (`RateLimitMiddleware` + `DEFAULT_RULES`), wired in `create_app()`.
  Design decisions, each recorded in the code:
  - **Redis, not in-process** — Render runs several Uvicorn workers, and a per-process counter would let
    N workers serve N times the configured limit.
  - **Fixed window, not a sliding log** — one `INCR` plus one `EXPIRE` per request. It permits up to 2x
    the limit across a window boundary, which is acceptable for cost control.
  - **Fail open** — a Redis error allows the request. A limiter is a cost guard, not an authorization
    boundary, so an outage must not 429 the whole API; `/ready` already surfaces Redis health.
  - **`EXPIRE` on every request, not just the first** — a crash between `INCR` and `EXPIRE` would
    otherwise leave a key with no TTL, permanently blocking that caller.
  - **Identity = user id when a bearer token parses, else client IP.** Added a non-raising
    `decode_token_subject` to `app/core/security.py` for this. Without it, everyone behind one NAT
    shares a budget and one user can exhaust it for the rest.
  - **Middleware added *first*** so it sits innermost: Starlette makes the last-added middleware
    outermost, and a 429 emitted outside `CORSMiddleware` carries no `Access-Control-Allow-Origin`, so
    the browser would report an opaque network error instead of a readable 429.
  - Limits: chat 20/min, backtest 10/min, ingest 10/min, upload 10/min, auth (login+register) 10/min.
  - `RATE_LIMIT_ENABLED` (default true) exists because `httpx`'s ASGI transport reports one client
    address for every test, so a live budget would leak across tests; a new root `conftest.py` sets it
    false for the suite, and `tests/test_rate_limit.py` installs the middleware on its own app instead.
  - **Found and fixed while verifying:** `X-RateLimit-*` and `Retry-After` were invisible to the SPA.
    Only a six-header safelist is readable cross-origin, and the frontend is a different origin, so
    `fetch` saw `null` for all of them (measured: `[...r.headers.keys()]` returned only
    `content-length`, `content-type`). Added `expose_headers` to `CORSMiddleware`, covering
    `X-Request-ID` too — which had the same problem.

  Verified live against the running API, not just in tests: `/ready` still `{"db":"ok","redis":"ok",
  "status":"ok"}`; 12 logins from one IP returned `401 ×10` then `429 ×2` with
  `{"error":{"code":"RATE_LIMIT_EXCEEDED","message":"Rate limit exceeded: 10 requests per 60s. Retry in
  51s."}}`, `Retry-After: 51`, and `X-RateLimit-Remaining` counting `9,8,7,…,0`; a new window let the
  same IP through again. Identity separation confirmed by dumping the real Redis keys after a mixed run:
  `ratelimit:backtest:user:d689837c-…:1788619080 = 3` alongside `ratelimit:backtest:ip:127.0.0.1:1788619080 = 1`,
  both `ttl=30` — the authenticated caller and the anonymous one were counted in different buckets on the
  same route. 12 new tests in `tests/test_rate_limit.py` (window arithmetic, per-identity budgets, window
  rollover, `reset_after` countdown, fail-open with a broken client, 429 envelope + headers, headers on
  allowed responses, unmatched route, method specificity, bearer-vs-IP identity, forged token degrading to
  the IP bucket, and a `DEFAULT_RULES` guard so renaming a route can't silently drop its limit).
  Suite: **81 passed**, exit 0, coverage 66%. Ruff clean.
- **Task 11 — recharts equity curve: done.** Each COMPLETED row on the Backtests page now expands to an
  area chart of its stored `equity_curve` (`Show chart` / `Hide chart`, `aria-expanded` +
  `aria-controls`). Details worth knowing:
  - `recharts@3.2.1` added as a dependency. It is ~295 kB, so the chart component is behind
    `React.lazy` + `Suspense` — the main bundle stayed at 834.93 kB (was 833.40 kB) instead of growing
    to 1,129.86 kB, and `EquityCurveChart-*.js` (294.96 kB / 88.65 kB gzip) only loads on first expand.
  - **Warmup bars are filtered out.** The worker fetches ~100 days before `start_date` to prime
    indicators, and `next_with_warmup` suppresses trades over them, so those bars land in the stored
    curve as a flat run at the initial capital. On a real Jan–Dec 2024 AAPL run the raw curve was 319
    points starting 2023-09-25; the chart plots the 251 that fall inside the requested window.
  - `isAnimationActive={false}`: recharts reveals the area by widening a clip rect, and when the chart
    mounts inside a just-expanded row that rect stayed ~5 px wide, leaving an empty plot. Confirmed by
    reading the `animationClipPath-*` rect width (5.09 of 1000) before the fix, 1000 after.
  - Gradient ids come from `useId()`, not the up/down direction — SVG ids are document-global, so two
    charts open at once with a shared id both resolved to whichever `<defs>` mounted first.
  - A one-bar curve renders as a dot: with a single point there is no segment to stroke, so the plot
    was empty. (Backtests #1/#2 in the dev DB are single-point rows seeded by an earlier throwaway
    script, which is how this surfaced.)
  - Verified live against **real** runs, not the seeded rows: submitted AAPL 2024-01-02→2024-12-31
    (after ingesting 398 OHLCV rows from yfinance) → +2.30% return, green stroke `hsl(160 84% 39%)`,
    251 bars, curve path spanning the full 1000 px plot; and AAPL 2024-01-02→2024-05-01 → −3.35%, red
    stroke `hsl(0 72% 51%)`, 84 bars. With both expanded the two gradient ids differed (`_r_0_` vs
    `_r_2_`). Hovering mid-plot produced the custom tooltip: "Feb 28, 2024 / $9,986.11 / −0.14% vs.
    initial". `npm run build` clean (`tsc -b` included), `npm run lint` adds no new warnings.

- **Task 14 — `Idempotency-Key` on backtest submission: done.** `POST /api/v1/backtests` answers 202
  before the Celery job runs, so a double click, proxy replay, or a network error after the request was
  received previously produced a second identical run. Now: `Idempotency-Key` header → the repeat
  returns the original row and dispatches nothing; the same key with a different body is a 409.
  - Real guard is the DB, not the lookup: `UniqueConstraint(strategy_id, idempotency_key)` (migration
    `b7d2c4e19a03`), with `IntegrityError` → rollback → re-read the winner. Postgres treats NULLs as
    distinct, so keyless submissions are unaffected and keep creating a new run each time.
  - Scoped per strategy rather than globally, since strategies are user-owned — one caller's key can't
    collide with another's.
  - Ordering is a security property: the strategy-ownership check runs *before* the key lookup, or a
    caller could probe another user's `strategy_id` and read back a run they don't own. Ticker
    resolution also precedes it, because the stored row records `ticker_id`, not the submitted symbol,
    so the replay comparison needs it.
  - Found a real bug while testing the race path: after the `IntegrityError` rollback every ORM
    instance in the session is expired, so reading `strategy.id` for the post-rollback re-read attempted
    lazy IO and raised `MissingGreenlet`. That would have failed in production on a genuine race, not
    just in the test. Fixed by reading `strategy_id`/`ticker_id` out as plain ints before the insert.
  - Frontend mints one key per *intent* (`crypto.randomUUID()` in `StrategiesPage`), held across
    failures so a "try again" click after a timeout returns the original run, and cleared on success or
    on any form edit (a changed body with the same key is a 409 by design).
  - 13 new tests in `tests/test_backtest_idempotency.py` (Celery `send_task` stubbed, so dispatch count
    is directly observable): repeat key → 1 row / 1 dispatch; no key → 2 rows / 2 dispatches; different
    keys → independent; reused key with a different `start_date`/`end_date`/`initial_capital`/
    `commission`/`slippage`/symbol → 409 + no extra dispatch; key persisted on the row; a foreign
    `strategy_id` 400s with zero dispatches; the same key on a different strategy is independent; and
    the lost race returns the winner's row without queueing.
  - Suite: **94 passed, exit=0**, coverage **67%** (`app/services/backtest_service.py` 77%). Migration
    verified against the dev DB: `alembic upgrade head` → `b7d2c4e19a03`, column present as
    `varchar(255)` nullable, constraint `UNIQUE (strategy_id, idempotency_key)`, HNSW index still there.
    (`alembic check` still reports the known pgvector false positive documented in `c961f1f9fde9` — the
    raw-SQL HNSW index isn't in `Base.metadata`, so autogenerate always wants to drop it.)

- **Task 15 — Prometheus `/metrics`: done.** New `app/core/metrics.py` (registry + counters/histogram),
  `app/api/middleware/metrics.py` (recording middleware), and the route on the root health router next
  to `/health` and `/ready`, since scrapers expect `/metrics` outside `/api/v1`.
  - Hand-rolled rather than an auto-instrumentation package, for **label cardinality**. A Prometheus
    series is created per unique label combination and lives in memory forever, so labelling by raw
    request path would mint a permanent series per backtest id and per scanner-probed URL. Everything
    labels by the matched route *template*, and unmatched requests collapse into one `<unmatched>`
    bucket.
  - Getting that label right took a fix: Starlette's `route.path` is relative to the router the route
    was included from, so it read `/backtests/{backtest_id}` with no `/api/v1`, which would collide
    across routers. `route_label` recovers the prefix by aligning the template's segments to the *end*
    of the concrete path. Substituting parameter values into the path instead would misfire when a value
    equals a prefix segment.
  - Exported: `quantpilot_http_requests_total` (method/route/status), `..._request_duration_seconds`
    (histogram, buckets skewed low since most endpoints are tens-of-ms DB reads),
    `..._requests_exceptions_total`, `..._rate_limit_rejections_total{rule}` (by rule name, not caller —
    per-caller would be unbounded), and `..._backtest_submissions_total{outcome=queued|replayed}`, which
    makes the Task 14 idempotency feature observable.
  - Middleware is added last in `create_app`, so it is outermost: timing covers the whole stack and a
    429 or an escaped exception is still counted. `/metrics` excludes itself — a 15s scrape would
    otherwise dominate the counters and make the histogram describe the scrape.
  - Auth: open by default (what a scraper on a private network expects), gated behind
    `Authorization: Bearer <METRICS_TOKEN>` when that setting is non-empty, compared with
    `hmac.compare_digest` so the timing doesn't leak a prefix match. `render.yaml` sets
    `METRICS_TOKEN: generateValue: true`, because a Render web service is publicly reachable.
  - Dependency: `prometheus-client>=0.20.0` (resolved to 0.26.0). `.env.example` and the README
    observability section updated.
  - 12 new tests in `tests/test_metrics.py`, aimed at what fails silently: ten distinct ids produce one
    route label, three bogus paths produce one `<unmatched>` series, the mount prefix is present,
    `/metrics` is absent from its own counters, and the token gate rejects missing/wrong/non-bearer
    credentials. Suite: **106 passed, exit=0**, coverage **68%**.
  - Verified live against the running backend, not just in tests: `/metrics` returned
    `text/plain; version=1.0.0`, ids 424242 and 999111 collapsed onto
    `route="/api/v1/backtests/{backtest_id}"`, `/definitely-not-a-route` landed in `<unmatched>`. A
    13-submission burst (rule is 10/60s, 2 already spent) gave 8×202 then 5×429 with
    `rate_limit_rejections_total{rule="backtest"} 5.0`, and submissions read
    `{outcome="queued"} 9.0` / `{outcome="replayed"} 1.0` — the replay from a repeated
    `Idempotency-Key` returning backtest id 6 twice.
  - Dev DB side effect: those probes left backtests 6–14 QUEUED (no worker running). Left in place
    rather than deleted.

- **Task 16 — load test of `POST /api/v1/backtests`: done, and executed for real.** New
  `scripts/load_test_backtests.py`. Scope is the **submission path only**: the endpoint answers 202 once
  the row is committed and the Celery job is dispatched, so what is measured is auth, the strategy
  ownership lookup, ticker resolution, the OHLCV coverage check, the INSERT, and the broker publish. It
  never touches the chat or RAG endpoints — those spend Gemini quota, which is a hard external limit
  rather than a throughput question.
  - Two properties that make the numbers mean something. **A distinct `Idempotency-Key` per request**:
    reusing one would make every request after the first a Task 14 replay, which skips the insert and
    the dispatch and would measure the wrong path. And **`httpx.Limits` raised to match concurrency**:
    the client defaults to 10 keepalive connections, which would serialize anything above that and
    report a measurement of the client instead of the API.
  - `--cleanup` deletes exactly the rows the run created, matched on its own key prefix
    (`loadtest-<run-id>-`), so it cannot touch anything else in the dev DB. The target strategy and
    symbol are read from the DB up front, so an unseeded database fails with a clear message instead of
    producing a run of 400s that looks like a latency result.
  - Percentiles are nearest-rank, so every number reported is an actually observed latency rather than
    an interpolation between two samples.
  - **Measured** (200 requests, concurrency 20, against a local backend started with
    `RATE_LIMIT_ENABLED=false` on port 8010 — the default rule is 10 submissions/min per caller, so a
    run against a normally-configured API measures the rate limiter, not the endpoint; the script prints
    the 429 count either way so that mistake is visible rather than silent):

    ```
    wall clock        1.28s
    throughput        156.3 req/s
    status codes      {202: 200}

    latency, all responses (s)
      p50             0.0869
      p95             0.2138
      p99             0.2289
      min             0.0552
      max             0.2312
    ```

    All 200 were accepted, and `--cleanup` deleted exactly the 200 rows it created. No test asserts on
    these figures — they are a one-off measurement of this machine against a local Postgres and Redis,
    not a regression gate.

- **Task 17 — Redis caching for RAG query embeddings: done, no live Gemini call made.** New
  `app/core/cache.py` (a general `RedisJSONCache` + a module-singleton client, disposed from the app
  lifespan) and `app/ai/embedding_cache.py` (`CachedQueryEmbedder`, wired into `RetrievalService`).
  - Scope is **query** embeddings only. Every `RetrievalService.search` has to embed the question before
    it can run the pgvector search, and that is a billed Gemini call — while the same text under the same
    model always yields the same vector, and queries genuinely repeat (the eval harness replays a fixed
    question set, the agent calls `search_documents` more than once per turn, users rephrase and re-ask).
    Document embeddings are deliberately *not* cached: they are computed once at ingestion and stored in
    `document_chunks.embedding`, which already is the cache.
  - Key: SHA-256 of the whitespace-normalized query, plus the model id and output dimensionality —
    exported from `app/ai/embedding.py` as `EMBEDDING_MODEL`/`EMBEDDING_DIMENSIONS` so the two cannot
    drift apart. Hashed so key length is bounded and Redis holds no readable record of what was asked.
    Case is *not* folded (embeddings are case-sensitive, so folding would serve a vector for text that
    was never embedded). Not scoped per user either: the vector is a pure function of the text, and the
    ownership filter that decides which chunks a caller may see is in the SQL (`search_user_chunks`), so
    two users asking the same question share one entry and still get only their own documents back.
  - A decoded hit is validated (list, right length, numeric) before use, and an entry that fails is
    treated as a miss and overwritten. Without that, an entry written under a different dimensionality
    would be handed to a `Vector(768)` comparison and fail inside the SQL query instead of degrading to a
    recompute. Symmetrically, a bad vector from the embedder is never written.
  - Fail-open, matching the rate limiter: a Redis outage turns every lookup into a miss and every write
    into a no-op. A cache guards cost, not correctness, and `/ready` already reports Redis health.
  - 24-hour TTL — long, because the text→vector mapping never changes for a fixed model; the TTL is there
    to reclaim space for one-off questions, not to bound staleness. New metric
    `quantpilot_query_embedding_cache_total{outcome=hit|miss}`, so the saving is observable rather than
    assumed; absent / Redis-down / unusable all count as one `miss`, since the question the metric
    answers is "how many API calls did the cache fail to save".
  - 20 new tests in `tests/test_embedding_cache.py`, all against a fake Redis and a **counting stub
    embedder** — no test makes a live embedding call, so "N identical queries cost 1 call" is directly
    asserted. Covers the JSON round trip, mandatory TTL, fail-open on a broken client, an undecodable
    entry, key normalization/case-sensitivity/model+dimension inclusion/no-plaintext, wrong-dimension and
    non-numeric entries being recomputed, a bad embedder result never being cached, the hit/miss
    counters, and that `RetrievalService` actually wires the wrapper.
  - Suite: **126 passed, exit=0**, coverage **68%**.
  - Verified against the real dev Redis (still no Gemini call — counting stub as the embedder): two
    spellings of the same query returned identical 768-length vectors for **1** embedder call, the key
    was present with a **86400s** TTL, a deleted key read back as a miss, and pointing the cache at a
    dead port (`redis://127.0.0.1:6399/0`) logged `cache_unavailable` for both get and set and still
    returned a 768-length vector.
- **Task 18 — OpenAPI descriptions on every endpoint: done.** All 24 operations now carry a `summary`,
  a `description` and a `responses` map: the six `/api/v1` routers plus `/health` and `/ready` (the
  `/metrics` route was already documented in task 15).
  - Every claim was checked against the source rather than written from memory, which caught four
    wrong ones before they shipped: `/auth/register` fails with **409 + 422**, not 400; the indicator
    defaults are period 20 for SMA/**EMA**/Bollinger, not just SMA/Bollinger; `/market-data/{symbol}/ingest`
    treats `end` as **exclusive** (that is what yfinance does — `app/infrastructure/yfinance_adapter.py`),
    unlike the two read endpoints where it is inclusive; and chat messages do **not** populate
    `citations_json` (it is always null — citations are inline in the answer text as
    `[Source: <filename>, Page: <n>]`).
  - Two substantive fixes fell out of documenting the behaviour. `POST /api/v1/backtests` is rate
    limited but documented no 429. And the SSE chat endpoint advertised `application/json` — FastAPI
    infers the content type from the response class and `StreamingResponse.media_type` is `None` — so
    the one content type it never returns was the only one in the schema. Fixed with a three-line
    `SSEResponse` subclass that carries `media_type` on the class.
  - `tests/test_openapi.py` (4 tests) keeps it from going stale: every operation must have a summary
    and description, the SSE route must document `text/event-stream` only and its 403/404/429/502, and
    the documented 429s must agree with the limiter's `DEFAULT_RULES` **in both directions** — a limited
    endpoint without a documented 429, or a documented 429 on an unlimited endpoint, both fail. That
    cross-check is what found the backtests gap. These tests read the generated schema, so they are the
    only ones in the suite that need no Postgres.
- **Task 19 — Flower for Celery monitoring: done.** A `flower` service in `docker-compose.yml`
  (`mher/flower:2.0`, <http://localhost:5555>), `flower` in the `dev` extra for running it without
  Docker, and docs in README §8 and CLAUDE.md.
  - The part that actually matters is in `app/workers/celery_app.py`: `worker_send_task_events=True`
    and `task_send_sent_event=True`. Celery emits no task events by default, so a Flower service added
    on its own would have shown workers and queues but an empty task list — the dashboard would look
    installed and be useless. The publisher-side event is the one that makes a task queued to a queue
    nobody consumes (a worker started without `--queues=backtest`, the failure mode CLAUDE.md warns
    about) visible as sent-but-never-received. `tests/test_worker.py` asserts both flags, since
    nothing else would catch their removal.
  - Flower runs from its own image rather than ours, so the api and worker images stay free of a
    monitoring dependency, and it is deliberately **not** in `render.yaml`: no auth, an API that can
    revoke and terminate tasks, and task arguments visible in plain text — the same reasoning that put
    `METRICS_TOKEN` on `/metrics` in task 15.
- **Task 20 — managed Postgres in `render.yaml`: done.** Added the top-level `databases:` block
  (`quantpilot-db`, Postgres **16** to match the local `pgvector/pgvector:pg16` image, `ipAllowList: []`
  so nothing outside the blueprint can connect) and switched `DATABASE_URL` on **both** the API and the
  worker from `sync: false` to `fromDatabase`/`connectionString`.
  - Field names and semantics verified against Render's blueprint spec, not assumed: `connectionString`
    resolves to `postgresql://user:password@host:port/database` over the private network — which is
    exactly why it can be consumed verbatim, since the validator on `settings.database_url` rewrites
    that scheme to `postgresql+asyncpg://`. `postgresMajorVersion` is a string and immutable, and an
    empty `ipAllowList` blocks all external connections whereas omitting the key allows any IP that has
    the credentials. pgvector needs no manual step: `alembic upgrade head` runs as the owner and the
    first RAG migration does `CREATE EXTENSION IF NOT EXISTS vector`.
  - Net effect: a blueprint sync now provisions everything stateful and wires it up. The only values
    left to set by hand are the genuinely external ones — `GEMINI_API_KEY`, `CORS_ORIGINS`,
    `VITE_API_BASE_URL`.
- **Suite note for tasks 18–20 — the full suite could NOT be run for these three.** The preview channel
  is the only way to reach Postgres from here (the Bash sandbox refuses loopback sockets:
  `PermissionError` on 127.0.0.1:5432), and it was unavailable for the rest of this run — every call
  returned "claude-opus-5 is temporarily unavailable, so auto mode cannot determine the safety of
  mcp__Claude_Browser__preview_start", across ~15 minutes of retries. Reported rather than worked
  around, per CLAUDE.md.
  - What *did* run, in-sandbox: `ruff check .` and `ruff format --check .` clean over 182 files, and the
    **82 tests that need no database — 82 passed**, which includes all five new ones (4 in
    `tests/test_openapi.py`, 1 in `tests/test_worker.py`). The other 49 error at fixture setup with the
    sandbox `PermissionError`, which is the socket policy, not a failure. Total is 131 tests, up from 126.
  - Also checked by hand, since these are the only runtime-behaviour changes in the three tasks and both
    are covered by DB-backed tests: `SSEResponse(...)` emits byte-identical headers to the previous
    `StreamingResponse(..., media_type="text/event-stream")` (`content-type: text/event-stream;
    charset=utf-8`), so `tests/test_conversations.py:83` cannot have regressed; and the new Celery event
    flags only add an event publish on the broker the task dispatch already uses.
  - To confirm the full 131, with `docker compose up db redis -d` running:
    `pytest -q --cov --cov-report=term`.
- **End-of-run cleanup.** The scaffolding this run needed to work around the sandbox is gone: the six
  `.*-out.txt` capture files and `scripts/_dbtask.py` deleted, the seven temporary `.claude/launch.json`
  entries removed (`dbtask`, `migrate-cycle`, `pipinstall`, `npminstall`, `backend-nolimit`, `loadtest`,
  `pytest`) leaving the three real ones — `frontend`, `backend`, `worker` — and the
  `# temp autonomous-run artifacts` block dropped from `.gitignore`, keeping only the two entries that
  outlive the run (`.venv/`, `coverage.xml`). `AGENTS.md` at the repo root is untracked and was left
  alone: it is another tool's guidance file, not part of this run.

## Blocked

**Nothing.** No task was blocked, abandoned or reverted — the "revert after 2 failed fix attempts"
rule was never invoked, and every numbered task 0–20 is committed.

One caveat that is *not* a block but is the weakest evidence in this run: the full DB-backed suite
could not be re-run for **tasks 18–20**, because the preview channel (the only route to Postgres from
this sandbox) was unavailable for the rest of the run. What did run for those three: `ruff check` and
`ruff format --check` clean over 182 files, and **82 of 131 tests passed** — every test that needs no
database, including all 5 added by tasks 18–19 — with the other 49 erroring on the sandbox's
`PermissionError` when connecting to 127.0.0.1:5432, not on anything in the diff. The two runtime
behaviour changes in that span were hand-verified instead (see the suite note under task 20). Confirm
the full 131 with `docker compose up db redis -d` and `pytest -q --cov --cov-report=term`.

## Deferred — needs live API quota

- **Task 2 — `python scripts/run_eval.py`.** The `SystemMessage` fix is committed but unexecuted: one
  eval run invokes the agent (and embeddings) once per seeded question, which would burn most of the
  remaining Gemini quota. Run it when quota allows to confirm scores are unchanged or better.
