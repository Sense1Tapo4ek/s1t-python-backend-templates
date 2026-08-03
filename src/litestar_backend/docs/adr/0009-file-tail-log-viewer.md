---
status: accepted
date: 2026-06-01
---
# 0009 - File-tail log viewer supersedes the out-of-process sink

## Context
The log subsystem (first SQLite+FTS5, then a Valkey-Streams sink) was
~4,300 lines across two processes to deliver one capability a starter
template actually needs: view logs in the admin UI, live and historical.
The durable store, indexed search, query DSL, cursor pagination, retention
sweeps, and pub/sub fan-out all existed only to support that store.

## Decision
The canonical sink is stdout plus a rotating JSONL file (`LOG_FILE_PATH`).
A `FileLogReader` over a raw `LogFileSource` serves history (`tail -N`,
reverse-scroll by `(inode, offset)` cursor) and live tail (`follow`,
`tail -F` semantics). Level filter and substring search move client-side;
"load more" reads deeper into the file. Export streams the file. SQLite,
FTS5, Valkey Streams, the `log-sink` process, the query DSL, migrations, and
retention workers are removed. One process; Valkey stays only for metrics.

## Consequences
- + ~4,300 lines down to a single-process file reader; no DB, no bus on the log path.
- + Survives restart (the file persists); `APP_WORKERS` stays a free knob.
- + 12-factor: stdout is the canonical stream; the file is a convenience for the UI.
- − No indexed/full-text search over history; filters are client-side over loaded rows.
- − Live tail is best-effort across rotation (at-most-once in the gap).
- − Retention is the rotation policy's job (logrotate / docker), not the app's.

## Alternatives considered
- Keep SQLite+sink -- over-engineered for a template (the problem above).
- In-memory ring buffer -- loses history on restart; no back-scroll.
- Per-line DB without FTS -- still a writer process and a schema to maintain.
