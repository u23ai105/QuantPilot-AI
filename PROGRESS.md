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

## Blocked

_(none yet)_

## Deferred — needs live API quota

_(none yet)_
