# 0021 - Replace the Redis image with Valkey
Status: accepted
Date: 2026-06-08

## Context
The template uses a Redis-protocol store only as a transport: the
`litestar.channels` SSE backend and (Phase A) the `video_uploaded` Stream fed
by the outbox relay. Redis OSS relicensed (RSALv2/SSPL) in 7.4, which is a
risk for a starter template others fork and ship.

## Decision
Run the `valkey/valkey:8` image instead of Redis. Valkey is the Linux
Foundation fork, wire-identical to Redis 7.2 (RESP). Keep the Python client
`redis.asyncio` (`redis[hiredis]`) unchanged. Rename `RedisConfig` ->
`ValkeyConfig`, env prefix `REDIS_` -> `VALKEY_`; the DSN scheme stays
`redis://` (the client does not parse `valkey://`).

## Consequences
- + Sidesteps the licence-change risk with zero client-code change.
- + Drop-in for the Channels backend and Streams; no protocol differences hit.
- - The `redis://` DSN and `redis.asyncio` client names now mismatch the
    `valkey` service -- a documented cosmetic wart (see infra/valkey.md).

## Alternatives considered
- Stay on Redis OSS 7.2 (frozen) - no security updates; rejected.
- Switch client to `valkey-py` - needless churn; the redis client is wire-
  compatible and maintained.
