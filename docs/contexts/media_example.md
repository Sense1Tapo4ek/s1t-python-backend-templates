# media_example context

The golden example context in this template. For contributors learning how
to wire a full S-DDD context with a transactional outbox, asyncpg, Valkey
Streams, and a Litestar SSE feed.

Replaces the deleted `orders` and `db_example_sddd` examples as the primary
worked reference. Delete it when adapting the template; keep `db_example_litestar`
only if you also need the SQLAlchemy / advanced-alchemy pattern.

## Mental model

```
POST /videos (202)
  |
  +-- asyncpg tx:
  |     INSERT media.videos (status=PENDING)
  |     INSERT media.outbox_messages
  |
  +-- return VideoModel (source_key, status, uploaded_at)

OutboxRelay (lifespan background task, runs forever)
  |
  +-- asyncpg tx:  SELECT ... FOR UPDATE SKIP LOCKED
  |     XADD video_uploaded (Valkey Stream)
  |     UPDATE outbox_messages SET sent_at
  |
  +--> at-least-once, APP_WORKERS-safe

GET /videos/feed (SSE)
  |
  +-- litestar.channels subscription on VIDEOS_CHANNEL
      (nothing publishes here yet -- broadcast lands in a later phase)
```

Status transitions PENDING -> PROCESSING -> DONE/FAILED are owned by
`media_example` but triggered by a FastStream consumer in a later phase
(Phase C). Today, `MarkProcessing/Done/FailedUC` exist and are wired in
the facade; no HTTP route exposes them yet.

## Public surface

### Routes

| Method | Path | Request | Response | Status |
|:---|:---|:---|:---|:---|
| POST | `/videos` | `UploadVideoRequest` (source_key) | `VideoModel` | 202 |
| GET | `/videos` | `?limit=1-200` (default 50) | `list[VideoModel]` | 200 |
| GET | `/videos/feed` | — | SSE stream | 200 |

`POST /videos` increments the `videos_uploaded_total` Prometheus counter.

`GET /videos/feed` opens a subscription on the `videos` Litestar channel.
No events are published to it in Phase A; consumers can subscribe and wait.

### Config (`MEDIA_` prefix)

| Env var | Default | Notes |
|:---|:---|:---|
| `MEDIA_SCHEMA_NAME` | `media` | Postgres schema |
| `MEDIA_POOL_SIZE` | `4` | asyncpg pool max connections |
| `MEDIA_RECENT_LIMIT` | `50` | default cap on `GET /videos` |
| `MEDIA_RELAY_BATCH` | `100` | outbox rows per drain cycle |
| `MEDIA_RELAY_IDLE_SLEEP` | `0.5` | seconds to sleep when outbox is empty |

### Schema and tables

Migration `migrations/media/001-create-videos.sql` runs at lifespan start
via yoyo (psycopg3 backend).

```
schema media
  videos
    id          UUID PK
    source_key  TEXT NOT NULL
    status      TEXT NOT NULL   -- 'pending' | 'processing' | 'done' | 'failed'
    uploaded_at TIMESTAMPTZ NOT NULL
    ix_videos_uploaded_at (uploaded_at DESC)

  outbox_messages
    id          UUID PK
    event_type  TEXT NOT NULL
    payload     BYTEA NOT NULL
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    sent_at     TIMESTAMPTZ NULL
    ix_outbox_pending (created_at WHERE sent_at IS NULL)
```

### Domain

`Video` aggregate: status machine PENDING -> PROCESSING -> DONE/FAILED;
guarded `mark_processing()` / `mark_done()` / `mark_failed()` raise
`InvalidTransition` on illegal moves. `VideoUploaded` domain event.

### DI providers

| Provider | Scope | Contents |
|:---|:---|:---|
| `MediaInfraProvider` | APP | `MediaConfig`, `MediaPool`, `OutboxRelay`, `MediaLifespanManager` |
| `MediaWebProvider` | REQUEST | `MediaFacade` (acquires asyncpg connection per request) |

`MediaPool` is a named wrapper around `asyncpg.Pool` with its own DI key,
distinct from any pool another context might hold.

## Invariants & gotchas

- **Outbox is written in the same transaction as the video row.** If the tx
  rolls back, the outbox row disappears too. The relay delivers at-least-once;
  consumers must be idempotent.
- **`SELECT ... FOR UPDATE SKIP LOCKED`.** Multiple `APP_WORKERS` relay tasks
  can run concurrently without duplicating delivery: each grabs its own batch
  of un-sent rows and holds row-level locks until the batch is marked sent.
- **Status is owned here, transitions driven externally.** Only `media_example`
  writes `videos.status`. Phase C adds a FastStream consumer that calls
  `mark_processing` / `mark_done` / `mark_failed` via the facade after
  consuming the Valkey Stream. Do not write to `videos.status` from another
  context directly.
- **`videos_uploaded_total` is a module-level `Counter`.** It is registered
  with `prometheus_client` on first import; repeated `create_app()` calls in
  tests reuse the same series (no duplicate-registration error).
- **SSE feed is empty until Phase C.** `GET /videos/feed` establishes a
  subscription but receives no events today; nothing calls
  `channels.publish(VIDEOS_CHANNEL, ...)`.

## Pointers

- `src/media_example/` — full context source
- `migrations/media/001-create-videos.sql` — schema DDL
- [docs/infra/valkey.md](../infra/valkey.md) — Valkey wiring (outbox relay + Channels backend)
- [docs/infra/postgres.md](../infra/postgres.md) — asyncpg pool, search_path, migrations
- [docs/adr/0022-video-pipeline-transport-roles.md](../adr/0022-video-pipeline-transport-roles.md) — transport role decision
- [docs/adr/0024-media-example-golden-context.md](../adr/0024-media-example-golden-context.md) — why this replaced orders + db_example_sddd
- [docs/architecture.md](../architecture.md) — S-DDD layers, DI scopes, how to add a context
