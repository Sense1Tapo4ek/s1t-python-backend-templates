# infra: Valkey

How Valkey is configured and wired in this template. Audience: contributors
and operators wiring contexts that need cross-process messaging or caching.

## Version & why

`valkey/valkey:8` (compose service `valkey`). Valkey is an open-source
Redis-compatible key/value store (wire-identical to Redis 7). It replaced
the Redis image to avoid licence-change risk; see [ADR 0021](../adr/0021-redis-to-valkey.md).

The Python client is **`redis.asyncio`** (`redis[hiredis]`), retained
unchanged — Valkey speaks the Redis RESP protocol, so the client requires
no modification.

## Configuration (`VALKEY_` prefix)

`ValkeyConfig` in `src/shared/config.py`. One Valkey, configured once,
reused across contexts.

| Env var | Default | Notes |
|:---|:---|:---|
| `VALKEY_HOST` | `localhost` | |
| `VALKEY_PORT` | `6379` | |
| `VALKEY_DB` | `0` | logical database index |
| `VALKEY_PASSWORD` | _(none)_ | optional |
| `VALKEY_MAX_CONNECTIONS` | `20` | pool ceiling |

`ValkeyConfig.url` produces a `redis://[:password@]host:port/db` DSN.
`.env.full.example` is the contract; `.env` is gitignored.

## Where it touches code

- `src/shared/config.py` — `ValkeyConfig` (env prefix `VALKEY_`, `url` property).
- `src/shared/adapters/driven/valkey/engine.py` — `build_valkey_client(url, *, max_connections, socket_timeout)` returns `redis.asyncio.Redis.from_url(url, decode_responses=True, ...)`.
- `src/root/composition/app.py` — `build_app` constructs `ChannelsPlugin(backend=RedisChannelsStreamBackend(history=0, redis=build_valkey_client(valkey_cfg.url)), channels=[VIDEOS_CHANNEL])`. This client is owned by the plugin and started/stopped via the app lifecycle.
- `src/media_example/adapters/driven/outbox_relay.py` — `OutboxRelay` calls `valkey.xadd(VIDEO_UPLOADED_STREAM, ...)` to publish drained outbox rows to the `video_uploaded` Valkey Stream.
- Future phases (FastStream consumer, SAQ): those will inject `aioredis.Redis` from the DI-managed client in `SharedProvider`.

## Two clients, on purpose

There are two distinct Valkey clients in the running app:

1. The `SharedProvider`-managed `aioredis.Redis` (APP scope, `aclose()` on shutdown) — for DI injection into contexts (e.g. `OutboxRelay`).
2. The `ChannelsPlugin`-owned client — `litestar.channels` manages its backend connection lifecycle itself; the client is built inline in `build_app`, not pulled from DI.

Do not route the Channels backend through the DI-managed client; the plugin
expects to own its connection.

## Local & test

`docker compose up` brings up Valkey (`valkey/valkey:8`) alongside Postgres
and the app. Integration/e2e tests spin a Valkey testcontainer via the
session-scoped `valkey_url` fixture (`tests/conftest.py`), which exports
`VALKEY_HOST` / `VALKEY_PORT`.

## Gotchas

- **`decode_responses=True`.** `build_valkey_client` always sets this flag. Values come back as `str`, not `bytes`. Code that assumes bytes will break; keep it consistent.
- **Channels backend uses `history=0`.** The SSE feed delivers only events published while a subscriber is connected. No replay, no persistence.
- **Valkey is a transport, not a system of record.** The transactional outbox in Postgres is the durable layer; Valkey Streams carry the notification. A lost Valkey event is survivable; the source of truth is the DB.
- **`redis://` DSN scheme.** `ValkeyConfig.url` emits `redis://...`. The `redis.asyncio` client does not recognise a `valkey://` scheme; the wire protocol is identical so `redis://` works.
