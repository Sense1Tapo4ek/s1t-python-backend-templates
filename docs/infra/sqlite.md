# SQLite

Version: bundled with Python (≥3.12 ships ≥3.40). Async access via
`aiosqlite`.

For the *why*, see [adr/0003-sqlite-wal-readers.md](../adr/0003-sqlite-wal-readers.md).
For schema management, see [infra/yoyo.md](yoyo.md).

## Where it's used

Single database file backs the admin log subsystem:
`${VOLUME_PATH}/logs/admin_logs.db`. No other context uses SQLite today;
add a new database under `${VOLUME_PATH}/<name>.db` if you do.

## Configuration

`SQLiteConnection` (in `shared/adapters/driven/db/`) opens one writer
connection and a pool of reader connections. Wired by the admin/log
provider:

| Env var | Default | Effect |
|:---|:---|:---|
| `LOG_DB_READER_COUNT` | 4 | Reader pool size. Each reader holds one aiosqlite connection. |
| `VOLUME_PATH` | `./storage` | Parent of the `logs/` directory. |

PRAGMAs applied at open:
- `journal_mode=WAL` — readers don't block the writer.
- `synchronous=NORMAL` — durable enough for log data; saves fsyncs.
- `temp_store=MEMORY`, `mmap_size=...`, `cache_size=...`.

The cleanup worker periodically issues `PRAGMA wal_checkpoint` followed
by `PRAGMA optimize` to keep the WAL bounded and statistics fresh.

## Reader pool

- One writer connection (`connection.write()`), drained by `LogSinkWorker`.
- N reader connections (`connection.read()`), used by everything else
  (UI, SSE catch-up, FTS search, exports, readiness probe).
- `connection.read()` is an async context manager; each acquisition
  borrows a reader from a `BoundedSemaphore`.
- Healthcheck (`GET /health/ready`) calls `SELECT 1` through the reader
  pool to exercise both acquisition and SQLite responsiveness.

## FTS5

`logs_fts` mirrors `logs.raw_json` via INSERT/DELETE triggers (created
in `migrations/admin_log/0001_init.sql`). Tokenizer: `trigram`. The
`detail='none'` flag is intentionally **not** set — required for phrase
queries, at the cost of ~2× FTS index storage.

DSL free-text falls through to FTS5 phrase search via
`log_query_builder.py`.

## Invariants & gotchas

- **Single writer per process.** SQLite serialises writes; the sink
  worker is the only writer. `APP_WORKERS=1` is enforced by the CLI
  because the writer connection is per-process.
- **Long writes can stall the WAL checkpointer.** The cleanup worker
  batches deletes to keep transactions short.
- **Composite index column order.** `idx_logs_level_timestamp(level,
  timestamp)` covers both level-only and level+time-range queries via
  the leftmost prefix; a separate `idx_logs_level` would be redundant.
- **Reader pool starvation.** SSE polling cadence
  (`LOG_STREAM_POLL_INTERVAL_S`, default 3s) × N subscribers competes
  with UI queries for readers. Increase pool size if you scale SSE.
- **`.db` files are gitignored.** Drop `${VOLUME_PATH}/logs/admin_logs.db`
  to reset the store.

## Pointers

- ADR: [0003-sqlite-wal-readers.md](../adr/0003-sqlite-wal-readers.md)
- Code: `src/shared/adapters/driven/db/`,
  `src/admin/log/ports/driven/repos/sqlite_log_repo.py`,
  `src/admin/log/ports/driven/repos/log_query_builder.py`.
- Schema: `migrations/admin_log/0001_init.sql`
- aiosqlite docs: <https://aiosqlite.omnilib.dev/>
- SQLite WAL: <https://www.sqlite.org/wal.html>
- FTS5 trigram: <https://www.sqlite.org/fts5.html#the_experimental_trigram_tokenizer>
