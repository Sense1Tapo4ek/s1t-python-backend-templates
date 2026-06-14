# Observability

Three signals: logs, request traces, build identity. All three flow through
the same structlog pipeline and are visible to operators via `/health`,
the access log middleware, and the admin log dashboard.

## Logs

`structlog` configured in `src/shared/logging.py::configure_structlog`. It
renders each record to a single JSON line, then a stdlib `logging` formatter
feeds two handlers:

- `StreamHandler` -> stdout (12-factor capture, container log driver).
- `WatchedFileHandler(LOG_FILE_PATH)` -> the JSONL file the admin UI reads.

Both handlers receive the identical line. There is no queue, no second
process, no message bus on the log path. See
[contexts/admin-log.md](../contexts/admin-log.md).

```
   structlog factory --JSON line--+--> StreamHandler      -> stdout
                                   +--> WatchedFileHandler -> app.jsonl
                                                                  |
                                              external rotation (logrotate)
                                                                  v
                                       FileLogReader -> facade -> UI / SSE
```

Write-side invariants (line-length cap, `O_APPEND` atomicity, `WatchedFileHandler`
cost), layer rules, and event naming: [infra/structlog.md](../infra/structlog.md).

## Trace correlation

`TraceIdMiddleware` binds a `trace_id` to structlog contextvars for each HTTP
request, so every log line emitted during the request carries it; the admin
log viewer shows it in the row drilldown (no server-side DSL filter).

Header (`X-Trace-Id`):
- Reads the incoming `X-Trace-Id` when present; otherwise generates a fresh
  16-char hex id.
- Echoes `X-Trace-Id` on the response so an upstream proxy can correlate.

`snitchbot` keeps its own request-context id, intentionally not unified.

## Access log

`AccessLogMiddleware` records one `http_request` line per response with
`method`, `path`, `status`, `duration_ms`, `trace_id`. Cheap; safe in
prod. Health probes are filtered to keep log volume reasonable.

## Build info

Reported via `GET /health` and the dashboard's "Build" panel. See
[contexts/admin.md](../contexts/admin.md) for resolution order, Docker /
GitHub Actions setup, response shape, and the rationale for `BuildInfoVo`.

## Health & readiness

`/health` (liveness) and `/health/ready` (readiness; probes log dir writability,
Postgres, and Valkey concurrently; returns a per-dependency `checks` map; 503
when any check fails, removing the replica from the LB pool without restarting
it) — semantics in [contexts/admin.md](../contexts/admin.md#two-tier-health).
`/ping` is a sync heartbeat with no I/O.

## Crash reporting

`snitchbot` is wired in `build_app` via `install_snitchbot(app)` and
configured in the structlog pipeline via `make_structlog_processor()`.
Set `SNITCHBOT_TOKEN` and `SNITCHBOT_CHAT_ID` (and unset `SNITCHBOT_DISABLED`)
to forward exceptions and selected events to a Telegram chat. Disabled by
default.

Interaction with `ProblemDetailsPlugin` and `enable_for_all_http_exceptions`:
[error hierarchy](error_hierarchy.md#snitchbot-interaction).

## Query observability

`build_engine` attaches `before/after_cursor_execute` SQLAlchemy Core listeners to
`engine.sync_engine`. Every statement is timed and recorded into the
`db_query_duration_seconds` Prometheus histogram (visible on `/metrics`). Statements
at or above `SLOW_QUERY_S` (default 0.1 s) are also logged at WARNING via structlog
with the event `"db query slow"`, `duration_ms`, and a whitespace-collapsed,
truncated statement template (no bound parameter values -- no PII). The probe engine
(`build_probe_engine`) is separate and uninstrumented by construction.

Module: `src/shared/adapters/driven/postgres/observability.py`.

## Pointers

- Code: `src/shared/logging.py`, `src/shared/adapters/middleware/`
- Admin log subsystem: [contexts/admin-log.md](../contexts/admin-log.md)
- Metrics subsystem: [subsystems/metrics.md](metrics.md) -- Prometheus
  endpoint and admin dashboard. Independent surface; do not duplicate
  signals here.
- structlog pipeline reference: [infra/structlog.md](../infra/structlog.md)
- Build info / dashboards: [contexts/admin.md](../contexts/admin.md)
