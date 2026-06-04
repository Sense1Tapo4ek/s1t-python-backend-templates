# Redis

How Redis is used in this template and how to configure it. For operators and
contributors wiring contexts that need cross-process messaging or caching.

## Version & why

`redis[hiredis] >= 5.0` (the `redis.asyncio` client; `hiredis` for faster
parsing). Added in Phase 1 of the event-driven showcase as the backend for
`litestar.channels` (the live order feed in the `orders` context), and as the
shared infrastructure for the planned Phases 2-3 (`jobs_saq` over a Redis-backed
queue, `streaming_faststream` over Redis Streams). See
[ADR 0020](../adr/0020-realtime-litestar-event-bus-channels.md).

## Configuration (`REDIS_` prefix)

Shared `RedisConfig` in `src/shared/config.py`. One Redis, configured once,
reused across contexts.

| Env var | Default | Notes |
|---|---|---|
| `REDIS_HOST` | `localhost` | |
| `REDIS_PORT` | `6379` | |
| `REDIS_DB` | `0` | logical database index |
| `REDIS_PASSWORD` | _(none)_ | optional |
| `REDIS_MAX_CONNECTIONS` | `20` | pool ceiling for `build_redis_client` |

`RedisConfig.url` composes a `redis://[:password@]host:port/db` DSN from these
fields. `.env.example` is the contract; `.env` is gitignored.

## Where it touches code

- `src/shared/config.py` — `RedisConfig` (the `REDIS_` settings + `url`).
- `src/shared/adapters/driven/redis/engine.py` — `build_redis_client(url)`
  returns `redis.asyncio.Redis.from_url(url, decode_responses=True, ...)`.
- `src/shared/provider.py` — `SharedProvider` provides `RedisConfig` and an
  async-generator `Redis` client (APP scope) that `aclose()`s on shutdown.
- `src/root/composition/app.py` — `build_app` constructs the
  `ChannelsPlugin(backend=RedisChannelsStreamBackend(history=0,
  redis=build_redis_client(RedisConfig().url)), channels=["orders"])`. This
  client is **owned by the plugin** and started/stopped via the app lifecycle.

## Two clients, on purpose

There are two distinct Redis clients in the running app, and that is
intentional:

1. The `SharedProvider`-managed `Redis` (APP scope, closed in the provider's
   generator) — for contexts that inject a Redis client directly (DI).
2. The `ChannelsPlugin`-owned client — `litestar.channels` manages its
   backend's connection lifecycle itself, so the channels client is built
   inline in `build_app`, not pulled from DI, and needs no manual close.

Do not try to route the Channels backend through the DI-managed client; the
plugin expects to own its connection.

## Local & test

- `docker compose up` brings up Redis alongside Postgres and the app.
- Integration/e2e tests use a Redis testcontainer via the session-scoped
  `redis_url` fixture (`tests/conftest.py`), which exports `REDIS_HOST` /
  `REDIS_PORT`; the e2e app fixture pins them so `build_app`'s Channels client
  points at the container. Set `REDIS_URL` to reuse an external Redis instead.

## Gotchas

- `decode_responses=True` — values come back as `str`, not `bytes`. Code that
  assumes bytes will break; keep it consistent.
- The Channels backend uses `history=0`: the SSE feed delivers only events
  published while a subscriber is connected. No replay, no persistence.
- Redis here is a transport/cache, not a system of record. Nothing durable
  depends on it in Phase 1.
