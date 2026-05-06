import asyncio
import sys
import time
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


class _QueueLogger:
    """Sink-side logger: serialized JSON in, asyncio.Queue out.

    `put_nowait` can raise `QueueFull` when the consumer (LogSinkWorker)
    is slower than producers. We can't push to the same queue to report
    the drop — that would amplify the back-pressure. Stderr is the
    fallback channel, throttled so a sustained overload doesn't flood it.
    """

    _dropped_total = 0
    _last_warning_at = 0.0

    def __init__(
        self,
        queue: asyncio.Queue[str],
        app_name: str,
        name: str = "",
    ) -> None:
        self._queue = queue
        self._app_name = app_name
        self.name = name

    def msg(self, *args: Any, **_kwargs: Any) -> None:
        if not args:
            return
        message = args[-1]
        try:
            self._queue.put_nowait(message)
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
    def __init__(self, queue: asyncio.Queue[str], app_name: str) -> None:
        self._queue = queue
        self._app_name = app_name

    def __call__(self, *args: Any) -> Any:
        return _QueueLogger(
            self._queue,
            self._app_name,
            name=args[0] if args else "",
        )


def _orjson_serializer(obj: Any, **_: Any) -> str:
    return orjson.dumps(obj).decode()


def configure_structlog(queue: asyncio.Queue[str], app_name: str) -> None:
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
    ]
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.dict_tracebacks,
            make_structlog_processor(),
            structlog.processors.JSONRenderer(serializer=_orjson_serializer),
        ],
        logger_factory=QueueLoggerFactory(queue, app_name),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
