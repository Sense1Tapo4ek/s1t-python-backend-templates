from enum import Enum

import structlog


class Layer(Enum):
    """Hexagon layer bound onto a logger as the `layer` field.

    No DOMAIN member: the domain layer is pure and never logs. Kept identical
    to the backend's shared/logging.py so `layer` reads the same across both
    services (the video_id-keyed correlation chain spans them).
    """

    APP = "app"
    PORTS_DRIVING = "ports_driving"
    PORTS_DRIVEN = "ports_driven"
    ADAPTERS_DRIVING = "adapters_driving"
    ADAPTERS_DRIVEN = "adapters_driven"


def layer_logger(layer: Layer, component: str) -> structlog.stdlib.BoundLogger:
    """Return a component logger pre-bound with its hexagon `layer` value."""
    return structlog.get_logger(component).bind(layer=layer.value)


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        cache_logger_on_first_use=True,
    )
