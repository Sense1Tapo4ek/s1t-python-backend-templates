# structlog

Version: per `pyproject.toml`. Documentation: <https://www.structlog.org/>.

Configured once at lifespan start in
`src/shared/logging.py::configure_structlog`. JSON output via `orjson`,
async-safe via a per-process `asyncio.Queue[str]` drained by the admin/log
sink worker.

For the consumer side, see [contexts/admin-log.md](../contexts/admin-log.md).
For the broader signal model, see [subsystems/observability.md](../subsystems/observability.md).

## Pipeline

In order:

1. `structlog.contextvars.merge_contextvars` — pulls `trace_id` /
   `span_id` from the contextvars set by `TraceIdMiddleware`.
2. `structlog.stdlib.add_log_level`.
3. `structlog.stdlib.add_logger_name`.
4. `structlog.processors.TimeStamper(fmt="iso", utc=True)`.
5. `structlog.processors.StackInfoRenderer`.
6. `CallsiteParameterAdder([PATHNAME, LINENO, FUNC_NAME])` — code location
   for navigation in the dashboard.
7. `structlog.processors.dict_tracebacks` — exceptions become a
   structured dict, never a string.
8. `make_structlog_processor()` from `snitchbot` — forwards selected
   events to Telegram when configured.
9. `structlog.processors.JSONRenderer(serializer=_orjson_serializer)`.

`logger_factory=QueueLoggerFactory(queue)` directs each rendered line
into the queue; `wrapper_class=structlog.stdlib.BoundLogger` keeps the
stdlib logging API for code that wants it.

## Queue sink

`_QueueLogger.put_nowait` enqueues. On `QueueFull`:
- Drops the message.
- Increments `_dropped_total`.
- Emits one stderr line per second max:
  `[litestar-base] log queue full, dropped (total=N)`.

Stderr is the only fallback that can't loop back through the sink.

## Logging conventions

Per `~/.claude/rules/s-ddd_python/logging.md`:

```python
log.info("user paid", user_id=user_id, amount=amount, currency=currency)
```

- Event name = stable literal. No f-strings, no IDs, no values inside
  the string.
- Dynamic values go in kwargs. snake_case keys; suffixes for units
  (`_ms`, `_bytes`, `_count`).
- Reserved keys (do **not** override): `event`, `level`, `timestamp`,
  `logger`, `exception`, `trace_id`, `span_id`.

| Layer | Logging |
|:---|:---|
| Domain | forbidden |
| App | trace only |
| Ports | forbidden |
| Adapters | full |

| Error type | Log level |
|:---|:---|
| `DomainError` (4xx) | WARNING |
| `AppError` (4xx) | WARNING |
| `PortError` (5xx) | ERROR + traceback |
| Unknown `Exception` | EXCEPTION (full traceback) |

## Invariants & gotchas

- **Queue size is finite.** The structlog sink does not back-pressure
  producers; it drops on overflow.
- **mypy + processor protocol.** structlog's processor protocol is wide
  enough that mypy can't infer types from a literal list. The
  `shared_processors` list is annotated `list[Any]` to keep the spread
  below readable.
- **Bind context with `contextvars`, not bound loggers**, when crossing
  async tasks — bound loggers don't propagate across task boundaries.
- **No PII in raw values.** If a field is sensitive, redact in a
  structlog processor before `JSONRenderer`.

## Pointers

- Code: `src/shared/logging.py`
- Consumer: [contexts/admin-log.md](../contexts/admin-log.md)
- Conventions: `~/.claude/rules/s-ddd_python/logging.md`
- structlog docs: <https://www.structlog.org/en/stable/>
