import asyncio
import logging
import logging.handlers
import sys
import time
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import orjson
import structlog
from snitchbot.integrations import make_structlog_processor
from structlog.processors import CallsiteParameter, CallsiteParameterAdder

# How often the queue logger may emit a `dropped` warning to stderr.
# A QueueFull burst can drop thousands of messages per second; we don't
# want stderr to become the new sink. One line per second is enough to
# alert an operator that the sink is back-pressured.
_DROP_WARNING_THROTTLE_S = 1.0

# Columns extracted on the producer side and shipped as XADD fields. Mirrors
# the `logs` table schema so the sink can INSERT without re-parsing JSON.
_COLUMN_KEYS: tuple[str, ...] = (
    "timestamp",
    "level",
    "logger",
    "event",
    "pathname",
    "lineno",
    "func_name",
    "trace_id",
    "span_id",
)

# Type alias for the payload carried through the local buffer: the
# pre-extracted column map (str → str for predictability) and the full
# event_dict serialised as bytes for the `raw_json` column and pub/sub
# fan-out.
LogPayload = tuple[dict[str, str], bytes]


class _QueueLogger:
    """Producer-side logger: structured payload in, local asyncio.Queue out.

    The final processor in the structlog pipeline (`_ColumnExtractor`)
    returns a `LogPayload` tuple; structlog passes it as the last positional
    argument to this logger's level methods, which all dispatch to `msg`.

    `put_nowait` can raise `QueueFull` when the sink reader is slow
    and the buffer fills. We can't push to the same queue to report the
    drop — that would amplify the back-pressure. Stderr is the fallback
    channel, throttled so a sustained overload doesn't flood it.
    """

    _dropped_total = 0
    _last_warning_at = 0.0

    def __init__(
        self,
        queue: asyncio.Queue[LogPayload],
        app_name: str,
        name: str = "",
    ) -> None:
        self._queue = queue
        self._app_name = app_name
        self.name = name

    def msg(self, *args: Any, **_kwargs: Any) -> None:
        if not args:
            return
        payload = args[-1]
        try:
            self._queue.put_nowait(payload)
        except asyncio.QueueFull:
            self._record_drop()

    def _record_drop(self) -> None:
        cls = type(self)
        cls._dropped_total += 1
        now = time.monotonic()
        if now - cls._last_warning_at < _DROP_WARNING_THROTTLE_S:
            return
        cls._last_warning_at = now
        print(
            f"[{self._app_name}] log queue full, dropped (total={cls._dropped_total})",
            file=sys.stderr,
        )

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return self.msg


class QueueLoggerFactory:
    def __init__(self, queue: asyncio.Queue[LogPayload], app_name: str) -> None:
        self._queue = queue
        self._app_name = app_name

    def __call__(self, *args: Any) -> Any:
        return _QueueLogger(
            self._queue,
            self._app_name,
            name=args[0] if args else "",
        )


class _ColumnExtractor:
    """Final structlog processor.

    Replaces `JSONRenderer`. Splits the event_dict into two halves:

    - a small `cols` map of fixed-schema columns, ready to be XADD'd as
      individual stream fields; sink reads them directly without parsing.
    - the full event_dict serialised once as JSON bytes, kept under the
      `raw` field for the `raw_json` SQLite column and pub/sub fan-out
      (the live-tail subscribers still receive a full JSON document).

    structlog interprets the return value of the final processor: a plain
    tuple is treated as `(positional_args, kwargs)` for the logger call,
    which would split our `(cols, raw)` payload into mismatched halves.
    We wrap it in the `((payload,), {})` shape so structlog passes the
    whole payload as a single positional argument to `_QueueLogger.msg`.

    Why orjson and not msgspec: structlog hands us an arbitrary `dict`, not
    a typed Struct — orjson is the faster path for that shape and is
    already configured here.
    """

    def __call__(
        self,
        _logger: Any,
        _name: str,
        event_dict: MutableMapping[str, Any],
    ) -> tuple[Any, ...]:
        cols = {key: _stringify(event_dict.get(key)) for key in _COLUMN_KEYS}
        raw = orjson.dumps(dict(event_dict))
        return ((cols, raw),), {}


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


class _TruncatingProcessorFormatter(structlog.stdlib.ProcessorFormatter):
    def __init__(self, *args: Any, max_line_bytes: int, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._max = max_line_bytes

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        encoded = rendered.encode("utf-8")
        if len(encoded) <= self._max:
            return rendered
        # Truncate on a byte budget, then repair UTF-8 by ignoring a torn
        # trailing multibyte sequence. The result is no longer valid JSON
        # but is one line and bounded — the reader skips it as malformed.
        return encoded[: self._max].decode("utf-8", "ignore")


def configure_structlog(
    *,
    app_name: str,
    log_file_path: Path,
    max_line_bytes: int,
) -> None:
    # structlog's processor protocol is wide enough that mypy can't infer
    # it from a literal list — annotate as Any-typed list so the spread
    # below stays single-source.
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        CallsiteParameterAdder([
            CallsiteParameter.PATHNAME,
            CallsiteParameter.LINENO,
            CallsiteParameter.FUNC_NAME,
        ]),
        structlog.processors.dict_tracebacks,
        make_structlog_processor(),
    ]

    structlog.contextvars.bind_contextvars(app=app_name)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = _TruncatingProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processor=structlog.processors.JSONRenderer(),
        max_line_bytes=max_line_bytes,
    )

    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    # WatchedFileHandler re-stats the path on every emit and reopens when
    # the inode changes -> picks up external rotation (logrotate / docker).
    # POSIX-only; on non-POSIX fall back to FileHandler (no rotation
    # detection).
    file_handler: logging.Handler
    try:
        file_handler = logging.handlers.WatchedFileHandler(
            str(log_file_path), encoding="utf-8"
        )
    except OSError:
        file_handler = logging.FileHandler(str(log_file_path), encoding="utf-8")
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [stream_handler, file_handler]
    root.setLevel(logging.INFO)
