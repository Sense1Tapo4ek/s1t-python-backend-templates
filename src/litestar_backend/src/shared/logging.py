import logging
import logging.handlers
import sys
from enum import Enum
from pathlib import Path
from typing import Any

import structlog
from snitchbot.integrations import make_structlog_processor
from structlog.processors import CallsiteParameter, CallsiteParameterAdder


class Layer(Enum):
    """Hexagon layer bound onto a logger as the `layer` field.

    No DOMAIN member: the domain layer is pure and never logs. Transport and
    composition edges (access log, trace middleware, lifespan) are not a
    context's hexagon layer either and keep their bare component loggers.
    """

    APP = "app"
    PORTS_DRIVING = "ports_driving"
    PORTS_DRIVEN = "ports_driven"
    ADAPTERS_DRIVING = "adapters_driving"
    ADAPTERS_DRIVEN = "adapters_driven"


def layer_logger(layer: Layer, component: str) -> structlog.stdlib.BoundLogger:
    """Return a component logger pre-bound with its hexagon `layer` value."""
    return structlog.get_logger(component).bind(layer=layer.value)


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
        # but is one line and bounded -- the reader skips it as malformed.
        return encoded[: self._max].decode("utf-8", "ignore")


def configure_structlog(
    *,
    app_name: str,
    log_file_path: Path,
    max_line_bytes: int,
) -> None:
    # structlog's processor protocol is wide enough that mypy can't infer
    # it from a literal list -- annotate as Any-typed list so the spread
    # below stays single-source.
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        CallsiteParameterAdder(
            [
                CallsiteParameter.PATHNAME,
                CallsiteParameter.LINENO,
                CallsiteParameter.FUNC_NAME,
            ]
        ),
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
        file_handler = logging.handlers.WatchedFileHandler(str(log_file_path), encoding="utf-8")
    except OSError:
        file_handler = logging.FileHandler(str(log_file_path), encoding="utf-8")
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [stream_handler, file_handler]
    root.setLevel(logging.INFO)
