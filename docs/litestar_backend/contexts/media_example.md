# media_example context

The golden example context in this template. For contributors learning how
to wire a full S-DDD context with a transactional outbox, SQLAlchemy, Valkey
Streams, and a Litestar SSE feed.

Replaces the deleted `orders` and `db_example_sddd` examples as the primary
worked reference. Delete it when adapting the template; keep `db_example_litestar`
only if you also need the advanced-alchemy (Repository/Service) pattern. Both
contexts run on SQLAlchemy; media uses plain SQLAlchemy 2.0 (see ADR 0025).

## Mental model

```
POST /videos (202)
  |
  +-- SQLAlchemy session (one tx):
  |     INSERT media.videos (status=PENDING)
  |     INSERT media.outbox_messages
  |
  +-- return VideoModel (source_key, status, uploaded_at)

OutboxRelay (lifespan background task, runs forever)
  |
  +-- SQLAlchemy session:  SELECT ... FOR UPDATE SKIP LOCKED
  |     XADD video_uploaded (Valkey Stream)
  |     UPDATE outbox_messages SET sent_at
  |
  +--> at-least-once, APP_WORKERS-safe

video_status stream (from event_microservice)
  |
  +-- VideoStatusConsumer (lifespan background task, XREADGROUP loop)
  |     per-message: open session -> facade.mark_processing/done/failed
  |     ack on success, DomainError, AppError, or unknown type
  |     stay pending on PortError -> XAUTOCLAIM recovery (at-least-once)
  |
  +--> status machine transition -> _publish_best_effort(VIDEOS_CHANNEL) -> XACK

GET /videos/feed (SSE)
  |
  +-- litestar.channels subscription on VIDEOS_CHANNEL
      status UCs broadcast {video_id, status} post-commit (best-effort)
```

Status transitions PENDING -> PROCESSING -> DONE/FAILED are owned by
`media_example` and triggered by `VideoStatusConsumer`, which reads the
`video_status` Valkey Stream published by `event_microservice`.
`MarkProcessing/Done/FailedUC` apply the transition, persist, then
broadcast to the SSE channel best-effort (a lost broadcast only costs a
live-browser update).

## Public surface

### Routes

| Method | Path | Request | Response | Status |
|:---|:---|:---|:---|:---|
| POST | `/videos` | `UploadVideoRequest` (source_key) | `VideoModel` | 202 |
| GET | `/videos` | `?limit=1-200` (default 50), `?cursor=<token>` (optional) | `VideoPage {items, next_cursor}` | 200, 400 on bad cursor |
| DELETE | `/videos/{id}` | — | — | 204, 404 unknown id |
| GET | `/videos/feed` | — | SSE stream | 200 |

`POST /videos` increments the `videos_uploaded_total` Prometheus counter.

`GET /videos/feed` opens a subscription on the `videos` Litestar channel.
Each status transition broadcasts `{"video_id": "...", "status": "..."}` to
connected subscribers.

### Config (`MEDIA_` prefix)

| Env var | Default | Notes |
|:---|:---|:---|
| `MEDIA_SCHEMA_NAME` | `media` | Postgres schema |
| `MEDIA_POOL_SIZE` | `4` | SQLAlchemy engine pool size |
| `MEDIA_RELAY_BATCH` | `100` | outbox rows per drain cycle |
| `MEDIA_RELAY_IDLE_SLEEP` | `0.5` | seconds to sleep when outbox is empty |
| `MEDIA_STATUS_BATCH` | `100` | entries per XREADGROUP read |
| `MEDIA_STATUS_BLOCK_MS` | `1000` | XREADGROUP blocking timeout (ms) |
| `MEDIA_STATUS_CLAIM_IDLE_MS` | `60000` | idle threshold for XAUTOCLAIM recovery |

### Schema and tables

Migrations in `migrations/media/` run at lifespan start via yoyo (psycopg3
backend). `001` creates the schema; `002` replaces the single-column index with
the composite `(uploaded_at DESC, id DESC)` required for stable keyset paging;
`003` adds audit columns (`created_at`, `updated_at`, `deleted_at`) via shared
mixins and replaces the full keyset index with a partial one covering only active
rows (`WHERE deleted_at IS NULL`). Reads always filter `deleted_at IS NULL`.

```
schema media
  videos
    id          UUID PK
    source_key  TEXT NOT NULL
    status      TEXT NOT NULL   -- 'pending' | 'processing' | 'done' | 'failed'
    uploaded_at TIMESTAMPTZ NOT NULL
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()   -- migration 003
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()   -- migration 003
    deleted_at  TIMESTAMPTZ NULL                     -- migration 003; NULL = active
    ix_videos_active_keyset (uploaded_at DESC, id DESC WHERE deleted_at IS NULL)

  outbox_messages
    id          UUID PK
    event_type  TEXT NOT NULL
    payload     BYTEA NOT NULL
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    sent_at     TIMESTAMPTZ NULL
    ix_outbox_pending (created_at WHERE sent_at IS NULL)
```

ORM models `VideoRow` / `OutboxRow` (`ports/driven/orm_models.py`) mirror this
DDL. yoyo owns schema creation; the ORM only maps rows for queries (no
`create_all`).

### Domain

`Video` aggregate: status machine PENDING -> PROCESSING -> DONE/FAILED;
guarded `mark_processing()` / `mark_done()` / `mark_failed()` raise
`InvalidTransition` on illegal moves. `VideoUploaded` domain event.

### DI providers

| Provider | Scope | Contents |
|:---|:---|:---|
| `MediaInfraProvider` | APP | `MediaConfig`, `MediaDb`, `VideoStatusConsumer`, `OutboxRelay`, `MediaLifespanManager` |
| `MediaWebProvider` | REQUEST | `MediaFacade` (opens an `AsyncSession` per request) |

`MediaDb` is a named wrapper around the SQLAlchemy `AsyncEngine` +
`async_sessionmaker` with its own DI key, distinct from the bare `AsyncEngine`
`db_example_litestar` provides (same type, different context -- avoids a Dishka
key collision).

## Invariants & gotchas

- **Outbox is written in the same transaction as the video row.** The repos and
  the UoW share one `AsyncSession`, so the video INSERT and the outbox INSERT
  commit together; if the tx rolls back, both vanish. The relay delivers
  at-least-once; consumers must be idempotent.
- **`SELECT ... FOR UPDATE SKIP LOCKED`.** Multiple `APP_WORKERS` relay tasks
  can run concurrently without duplicating delivery: each grabs its own batch
  of un-sent rows and holds row-level locks until the batch is marked sent.
- **Status is owned here, transitions driven by the status stream.** Only
  `media_example` writes `videos.status`. `VideoStatusConsumer` calls
  `mark_processing` / `mark_done` / `mark_failed` via the facade after
  reading the `video_status` Valkey Stream. Do not write to `videos.status`
  from another context directly.
- **`videos_uploaded_total` is a module-level `Counter`.** It is registered
  with `prometheus_client` on first import; repeated `create_app()` calls in
  tests reuse the same series (no duplicate-registration error).
- **Duplicate status events are absorbed.** `InvalidTransition` on a repeated
  transition is caught, logged at WARNING, and the stream entry is acked.
  No dedup table is required.
- **SSE broadcast is best-effort.** `_publish_best_effort` swallows `PortError`
  after logging; a missed broadcast only costs a live-browser update and
  never causes a status-UC rollback.

## Pointers

- `src/media_example/` — full context source
- `src/media_example/adapters/driving/status_consumer.py` — XREADGROUP consumer
- `src/media_example/ports/driven/channels_feed_publisher.py` — SSE broadcast
- `src/media_example/ports/driving/status_events.py` — inbound event schema
- `src/media_example/ports/feed.py` — `VIDEOS_CHANNEL` constant
- `migrations/media/001-create-videos.sql` — schema DDL
- `migrations/media/002-videos-keyset-index.sql` — composite index for keyset pagination
- [docs/contract/video_status.md](../../contract/video_status.md) — wire contract for the return stream
- [docs/infra/valkey.md](../infra/valkey.md) — Valkey wiring (outbox relay + Channels backend)
- [docs/infra/postgres.md](../infra/postgres.md) — SQLAlchemy engine, search_path, migrations
- [docs/adr/0022-video-pipeline-transport-roles.md](../../adr/0022-video-pipeline-transport-roles.md) — transport role decision
- [docs/adr/0024-media-example-golden-context.md](../../adr/0024-media-example-golden-context.md) — why this replaced orders + db_example_sddd
- [docs/adr/0025-standardize-on-sqlalchemy.md](../../adr/0025-standardize-on-sqlalchemy.md) — single DB stack; plain SQLAlchemy here
- [docs/adr/0028-video-status-return-path.md](../../adr/0028-video-status-return-path.md) — why direct-publish over outbox for the return path
- [docs/architecture.md](../../architecture.md) — S-DDD layers, DI scopes, how to add a context
