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

## Blocked

_(none yet)_

## Deferred — needs live API quota

- **Task 2 — `python scripts/run_eval.py`.** The `SystemMessage` fix is committed but unexecuted: one
  eval run invokes the agent (and embeddings) once per seeded question, which would burn most of the
  remaining Gemini quota. Run it when quota allows to confirm scores are unchanged or better.
