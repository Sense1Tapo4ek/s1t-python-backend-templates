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

A write-side processor truncates each rendered line to `LOG_MAX_LINE_BYTES`
so one record is one `write` (relies on `O_APPEND` atomicity; single host,
POSIX). The reader skips malformed or oversized lines rather than failing the
request.

### Layer rules

Per `~/.claude/rules/s-ddd_python/logging.md`:

| Layer | Logging |
|:---|:---|
| Domain | forbidden |
| App | trace only (start/end of critical processes) |
| Ports | forbidden |
| Adapters | full |

Event names are stable literals. Dynamic values go in kwargs:

```python
log.info("user paid", user_id=user_id, amount=amount, currency=currency)
```

## Trace correlation

Every log line emitted during a request carries `trace_id` / `span_id`; the
admin log viewer shows them in the row drilldown (no server-side DSL filter).

Headers:
- Reads incoming `traceparent` (W3C Trace Context) when present; otherwise
  generates fresh ids.
- Emits `traceparent` on the response so an upstream proxy can chain.

## Access log

`AccessLogMiddleware` records one `http_request` line per response with
`method`, `path`, `status`, `duration_ms`, `trace_id`. Cheap; safe in
prod. Health probes are filtered to keep log volume reasonable.

## Build info

Reported via `GET /health` and the dashboard's "Build" panel. See
[contexts/admin.md](../contexts/admin.md) for resolution order, Docker /
GitHub Actions setup, and response shape.

`BuildInfoVo(app_name, started_at, commit_sha, branch, dirty)` is a single
VO because all five fields describe one process instance — splitting per
field would be noise (per S-DDD `domain.md` §3.1).

## Health & readiness

- `/health` — liveness. Always 200 while the process is alive.
- `/health/ready` — liveness-plus-config check. 503 on failure; logs
  `error_type` for diagnosis. (The log path is a plain file, so there is no
  DB pool to probe.)
- `/ping` — sync heartbeat, no I/O.

Failing `/health/ready` removes the replica from the load balancer
without restarting it.

## Crash reporting

`snitchbot` is wired in `create_app` via `install_snitchbot(app)` and
configured in the structlog pipeline via `make_structlog_processor()`.
When `SNITCHBOT_TELEGRAM_*` env vars are set, exceptions and selected
events are forwarded to a Telegram channel. Disabled by default.

A required workaround lives in `_http_exception_handler`: snitchbot's
`install()` registers a generic `Exception` handler that re-raises
`HTTPException`, which Litestar converts to a bare 500. The catch-all
restores the original status code and detail.

## Pointers

- Code: `src/shared/logging.py`, `src/shared/adapters/middleware/`
- Admin log subsystem: [contexts/admin-log.md](../contexts/admin-log.md)
- Metrics subsystem: [subsystems/metrics.md](metrics.md) — Prometheus
  endpoint and admin dashboard. Independent surface; do not duplicate
  signals here.
- structlog pipeline reference: [infra/structlog.md](../infra/structlog.md)
- Build info / dashboards: [contexts/admin.md](../contexts/admin.md)
