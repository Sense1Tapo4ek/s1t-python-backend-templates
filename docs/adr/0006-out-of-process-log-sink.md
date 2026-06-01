# 0006 — Move the log sink out of process onto Valkey Streams
Status: superseded by 0009
Date: 2026-05-11

## Context
The in-process `LogSinkWorker` (asyncio.Queue → SQLite) pinned the
template to `APP_WORKERS=1` because SQLite tolerates only one writer.
Adding any new long-lived process (scheduler, CLI ingestion, second
service) required reinventing the structlog pipeline. The single-process
constraint was load-bearing for observability but invisible to the
operator until they tried to scale.

## Decision
Producers ship structlog records via Valkey Streams. A dedicated
`log-sink` process (single consumer group `logsink`) is the only
`INSERT` path into `admin_logs.db`; it XACKs after commit and PUBLISHes
the persisted batch on a Valkey pub/sub channel that Litestar Channels'
Redis backend fans out to SSE subscribers in any web worker. One bus
(Valkey) carries both transports.

## Consequences
- + `APP_WORKERS` becomes a free knob; horizontal scale-out is trivial.
- + Any new process speaks structlog → Valkey → admin_logs.db with zero
  bespoke wiring.
- + At-least-once: XACK after commit means a sink crash mid-batch costs
  one re-delivery, not a loss.
- − Two services to run locally (Compose handles it; bare `uv run`
  needs two shells).
- − Live SSE entries carry `id=0` (real id is assigned in-sink and
  isn't echoed back); frontend dedups by `(timestamp, event)`.

## Alternatives considered
- **Subinterpreter** — PEP 734 `interpreters` is stdlib only from 3.13;
  3.12 forces `_xxsubinterpreters` (private). Rejected on stability.
- **Pub/sub instead of Streams** — fire-and-forget; sink restart loses
  in-flight entries. Streams + consumer group give durable replay.
- **Two backends (memory channels + separate writer)** — duplicates the
  bus and bifurcates ops. One Valkey instance covers both.
