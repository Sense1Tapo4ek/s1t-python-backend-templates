# 0002 — Litestar Channels as the in-process event bus
Status: accepted
Date: 2026-05-06

## Context
Two needs collide: SSE broadcast for the admin log tail, and a typed
domain event bus for cross-context decoupling. Both want pub/sub fan-out
inside the process. A starter template should not require Redis or
RabbitMQ for either.

## Decision
One `ChannelsPlugin(MemoryChannelsBackend, dropleft, arbitrary_channels=True)`
built in `create_app`, threaded into both `Litestar(plugins=[...])` and
`build_container(channels_plugin=...)`. The typed bus
(`shared/adapters/driven/event_bus`) is a thin layer over the same plugin
using `msgspec.json` payloads and `event:{module}.{QualName}` channel
names.

## Consequences
- + Zero infra dependencies; cross-process backend (Redis / Postgres
  LISTEN) is a one-line provider swap when needed.
- + Backpressure handled at the plugin level (`subscriber_max_backlog` +
  `dropleft` strategy) — slow consumers can never stall the writer.
- − Single-process only with `MemoryChannelsBackend` → enforces
  `APP_WORKERS=1`.
- − No persistence; events are lost on restart. Acceptable for an
  observability-only fan-out and the included starter; a real
  cross-process bus needs durable storage.

## Alternatives considered
- Redis pub/sub from day one — overkill for a starter; adds an op cost.
- Plain `asyncio.Queue` registry — works for one consumer, fails the
  moment SSE needs N subscribers per channel.
- Kafka / RabbitMQ — wrong tool inside a single process.
