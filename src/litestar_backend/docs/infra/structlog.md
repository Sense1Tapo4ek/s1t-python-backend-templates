# structlog

Version: per `pyproject.toml`. Documentation: <https://www.structlog.org/>.

Configured once at startup in `src/shared/logging.py::configure_structlog`.
structlog renders JSON; two stdlib `logging` handlers emit it — a
`StreamHandler` to stdout and a `WatchedFileHandler(LOG_FILE_PATH)` to the
JSONL file the admin log UI reads.

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
9. `structlog.stdlib.ProcessorFormatter.wrap_for_formatter` — terminal
   processor handing the event dict to the stdlib formatter.

`logger_factory=structlog.stdlib.LoggerFactory()`; the stdlib root logger
carries two handlers, each with
`ProcessorFormatter(processor=JSONRenderer(serializer=_orjson_serializer))`.
The `snitchbot` `make_structlog_processor()` stays in the chain before the
terminal wrapper.

## File handler & rotation

- `WatchedFileHandler` re-`stat()`s the file before every emit and reopens it
  if the inode changed — so external rotation (logrotate / docker) is picked
  up without restarting the app. POSIX-only; on non-POSIX fall back to plain
  `FileHandler` (no rotation detection).
- The app never rotates or deletes its own file. Rotation is operational.
  Example: `deploy/logrotate/app.conf` with `create`-mode (not
  `copytruncate`) so an open export fd reads a consistent inode.
- A write-side processor caps each rendered line at `LOG_MAX_LINE_BYTES`.

## Logging conventions

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

- **One line per record (JSONL).** A truncation processor keeps each line
  under `LOG_MAX_LINE_BYTES`; relies on `O_APPEND` single-write atomicity
  (single host, POSIX). Best-effort.
- **`WatchedFileHandler` cost.** It re-stats on every emit; acceptable for a
  template, measurable at very high volume.
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
- structlog docs: <https://www.structlog.org/en/stable/>
