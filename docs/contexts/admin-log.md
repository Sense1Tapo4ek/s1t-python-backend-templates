# admin/log

SQLite-backed log subsystem: capture, search, tail, export. Sub-context of
[admin](admin.md), kept separate so it can grow without bloating the
parent.

For the *why*, see [adr/0003-sqlite-wal-readers.md](../adr/0003-sqlite-wal-readers.md).

## Mental model

structlog → asyncio.Queue → sink worker → SQLite (WAL).
Reader pool (N=4) serves UI tail, SSE stream, FTS search, and exports.
A cleanup worker prunes rows older than retention.

```
log.info("user paid", ...)
       │
       ▼
QueueLogger.put_nowait(json) ──── shared/logging.py
       │
       ▼
LogSinkWorker.drain() ─────────── single writer, batched insert
       │
       ▼
SQLite WAL ──── logs (table)
              │
              └── logs_fts (FTS5 trigram, content='logs', auto-synced)
```

Read paths:

```
HTTP  ─── LogsApiController ─── LogsFacade ─── ILogReader ─── SQLiteLogRepo (reader pool)
SSE   ─── /api/v1/admin/logs/stream ─── stream_after() + ChannelsLogBroadcaster
Export ─── /api/v1/admin/logs/export?format=csv|ndjson ─── stream_query()
```

## Public surface

### Endpoints

| Path | Method | Purpose |
|:---|:---|:---|
| `/admin/logs/` | GET | HTML dashboard (LogsPageController). |
| `/api/v1/admin/logs/` | GET | JSON tail page; query string `q=` for DSL. |
| `/api/v1/admin/logs/older` | GET | Cursor-based pagination; pass `before=<id>`. |
| `/api/v1/admin/logs/stream` | GET | Server-Sent Events live tail. |
| `/api/v1/admin/logs/` | DELETE | Wipe all entries (admin only). |
| `/api/v1/admin/logs/export` | GET | Download all matches; `format=ndjson|csv`. |
| `/admin/logs/static/*` | GET | Bundled HTML/CSS/JS. 1h browser cache. |

All non-static endpoints require `Role.ADMIN`.

### Types

| Symbol | Where | Role |
|:---|:---|:---|
| `LogsFacade` | `ports/driving/facades/` | Read-side: page / older / stream / export / search. |
| `LogsAdminFacade` | `ports/driving/facades/` | Mutations: clear logs. |
| `ILogReader` | `app/interfaces/` | Driven contract. `tail`, `read_before`, `stream_after`, `stream_query`. |
| `LogFilterVo` | `domain/` | Immutable filter spec. Self-validates against `VALID_LEVELS`. |
| `LogEntryEnt` | `domain/` | One row, with `id: LogId`, raw JSON, parsed kwargs. |
| `LogPageResponseSchema` | `ports/driving/schemas/` | Wire shape: `entries`, `cursor`, `has_more`. |

## Search DSL

A small query language compiled to SQL by `domain/dsl_parser.py` →
`LogFilterVo`. The query string `q=` on `/api/v1/admin/logs/`, capped at 2048
chars.

| Token | Effect |
|:---|:---|
| `level:WARN+` | min level WARN; matches WARN/WARNING/ERROR/CRIT/CRITICAL via rank. |
| `level:INFO,ERROR` | exact match; OR-combined. |
| `logger:auth` | exact logger match. |
| `logger:auth.*` | descendants only (`auth.x`, `auth.x.y`, never `auth`). |
| `trace_id:abc123…` | full 16-char trace id. |
| `user_id=u1` | kv match against the raw_json kwarg. Key must match `[a-zA-Z0-9_.]+`. |
| `from:2026-05-01T00:00 to:2026-05-02T00:00` | ISO time range. |
| free text | passes through as FTS5 phrase. |

Failures: `DslSyntaxError` → 400 with parse position; `InvalidLogFilterError`
→ 400 with field/reason. Both have specialised handlers in
`admin/log/adapters/driving/error_handlers.py`.

## Configuration

```
LOG_RETENTION_DAYS=7
LOG_BATCH_SIZE=100              # rows per insert batch
LOG_BATCH_TIMEOUT_MS=100        # max wait before flushing partial batch
LOG_SSE_QUEUE_SIZE=100          # per-subscriber backlog
LOG_CLEANUP_INTERVAL_HOURS=24
LOG_TAIL_SIZE=200
LOG_HISTORY_CHUNK=200
LOG_DB_READER_COUNT=4
LOG_MAX_LIMIT=5000              # hard cap on any single SQL LIMIT
LOG_STREAM_POLL_INTERVAL_S=3.0  # SSE catch-up polling cadence
```

## Storage

One file at `${VOLUME_PATH}/logs/admin_logs.db`. Schema in
`migrations/admin_log/` — see [infra/yoyo.md](../infra/yoyo.md).

Two indexes carry the load:
- `idx_logs_level_timestamp(level, timestamp)` — covers level filter +
  time range, the dominant query shape.
- `logs_fts` — FTS5 trigram over `raw_json`, auto-synced via triggers.

## Invariants & gotchas

- **Single writer per process.** `LogSinkWorker` owns the connection.
  `APP_WORKERS=1` is enforced by the CLI.
- **Cursor semantics.** `cursor` returned by `tail`/`read_before` is the
  id of the **oldest** entry in the page. Pass it back as `before=` to
  fetch the previous page. `has_more=False` means no more rows behind.
- **`limit + 1` trick.** Repos request one extra row to compute
  `has_more` cheaply.
- **SSE catch-up gap.** Subscribers join the broadcast channel BEFORE
  draining the catch-up tail to avoid losing events that arrive between
  the two reads.
- **Drop-on-overflow on the structlog queue.** When the sink can't
  drain, `_QueueLogger` drops messages and emits a throttled stderr
  warning (1 line/sec) — never back-pressures the producer.
- **DELETE wipes everything.** No filter on the admin clear endpoint
  by design — partial wipes invite mistakes.

## Recipes

### Tighten retention

```
LOG_RETENTION_DAYS=3
```

`LogCleanupWorker` runs every `LOG_CLEANUP_INTERVAL_HOURS` and after
each batch of deletes runs `PRAGMA wal_checkpoint` + `PRAGMA optimize`.

### Add a level

Edit `LEVEL_RANK` in `admin/log/domain/dsl_constants.py`. `VALID_LEVELS`
and the SQL CASE in `log_query_builder.py` are derived.

### Replace the front-end

Static files live at `src/admin/log/adapters/driving/static/` and are
served by Litestar's `create_static_files_router` from
`/admin/logs/static/`. Override `LOG_STATIC_PATH` to point elsewhere.

## Pointers

- ADR: [0003-sqlite-wal-readers.md](../adr/0003-sqlite-wal-readers.md)
- Code: `src/admin/log/`
- Schema: `migrations/admin_log/0001_init.sql`
- Infra: [infra/sqlite.md](../infra/sqlite.md), [infra/yoyo.md](../infra/yoyo.md)
- Cross-cutting: [subsystems/observability.md](../subsystems/observability.md)
