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

## Blocked

_(none yet)_

## Deferred — needs live API quota

- **Task 2 — `python scripts/run_eval.py`.** The `SystemMessage` fix is committed but unexecuted: one
  eval run invokes the agent (and embeddings) once per seeded question, which would burn most of the
  remaining Gemini quota. Run it when quota allows to confirm scores are unchanged or better.
