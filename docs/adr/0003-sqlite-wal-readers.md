# 0003 — SQLite WAL with reader pool for the admin log store
Status: accepted
Date: 2026-05-06

## Context
The admin log subsystem needs cheap append + concurrent read-only queries
(UI tail, SSE stream, NDJSON/CSV export, FTS search) without standing up
a separate database server. Operationally the template must run with
`docker compose up` and a single SQLite file.

## Decision
SQLite in WAL mode. One process-wide writer (the sink worker drains an
`asyncio.Queue`); a pool of `aiosqlite` reader connections
(`log_db_reader_count`, default 4) handles all queries. FTS5 with the
trigram tokenizer indexes `raw_json` for substring search. Schema is
managed by yoyo-migrations under `migrations/admin_log/`.

## Consequences
- + Zero ops; atomic writes; readers don't block the writer.
- + FTS5 trigram answers DSL queries without a separate index.
- + The reader pool is tuned per-process via env; readiness probe
  exercises it with `SELECT 1`.
- − Single-writer design forces `APP_WORKERS=1` (see ADR 0002).
- − Long write transactions can stall the WAL checkpointer; the cleanup
  worker keeps deletes batched.

## Alternatives considered
- Postgres — better at concurrency, wrong for a single-binary starter.
- Plain JSON-lines on disk — no full-text search, no concurrent readers
  without rolling our own MVCC.
- DuckDB — analytical strengths irrelevant to row-by-row tail/SSE.
