# Autonomous run progress

Test command used for every task: full `pytest` suite via the preview channel (the Bash sandbox
cannot reach Postgres, so DB-backed tests only run there). Baseline at start of run: **63 passed**.

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

## Blocked

_(none yet)_

## Deferred — needs live API quota

- **Task 2 — `python scripts/run_eval.py`.** The `SystemMessage` fix is committed but unexecuted: one
  eval run invokes the agent (and embeddings) once per seeded question, which would burn most of the
  remaining Gemini quota. Run it when quota allows to confirm scores are unchanged or better.
