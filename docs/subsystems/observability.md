# Observability

Three signals: logs, request traces, build identity. All three flow through
the same structlog pipeline and are visible to operators via `/health`,
the access log middleware, and the admin log dashboard.

## Logs

`structlog` configured in `src/shared/logging.py::configure_structlog`.
JSON output via `orjson`, async-safe via a per-process queue drained by
the admin/log sink worker. See [contexts/admin-log.md](../contexts/admin-log.md).

Pipeline (in order):
1. `merge_contextvars` — pulls `trace_id` / `span_id` from contextvars.
2. `add_log_level`, `add_logger_name`.
3. `TimeStamper(fmt="iso", utc=True)`.
4. `CallsiteParameterAdder` — `pathname`, `lineno`, `func_name`.
5. `dict_tracebacks` — exception → structured dict, never a string.
6. snitchbot processor — forwards selected events to Telegram.
7. `JSONRenderer(serializer=_orjson_serializer)`.
8. `QueueLoggerFactory` — emits each rendered line into `asyncio.Queue[str]`.

The queue size is bounded; on overflow, `_QueueLogger` drops messages
and emits a throttled stderr warning (1 line/sec). Producers are never
back-pressured.

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

`TraceIdMiddleware` (in `shared/adapters/middleware/`) generates a
16-char hex `trace_id` per request, plus an 8-char `span_id`. Both bind
into `structlog.contextvars` via `merge_contextvars`, so every log line
emitted during the request carries them.

The admin log dashboard exposes `trace_id:` as a DSL filter — see
[contexts/admin-log.md](../contexts/admin-log.md).

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
- `/health/ready` — runs `SELECT 1` against the SQLite reader pool.
  503 on failure; logs `error_type` for diagnosis.
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
- structlog pipeline reference: [infra/structlog.md](../infra/structlog.md)
- Build info / dashboards: [contexts/admin.md](../contexts/admin.md)
