from enum import Enum

import structlog


class Layer(Enum):
    """Hexagon layer bound onto a logger as the `layer` field.

    No DOMAIN member: the domain layer is pure and never logs. Transport and
    composition edges (access log, trace middleware, lifespan) are not a
    context's hexagon layer either and keep their bare component loggers. Kept
    identical across both services so `layer` reads the same on every line of
    the video_id-keyed correlation chain that spans them.
    """

    APP = "app"
    PORTS_DRIVING = "ports_driving"
    PORTS_DRIVEN = "ports_driven"
    ADAPTERS_DRIVING = "adapters_driving"
    ADAPTERS_DRIVEN = "adapters_driven"


def layer_logger(layer: Layer, component: str) -> structlog.stdlib.BoundLogger:
    """Build a component logger bound with its hexagon `layer` value.

    App use cases build it inside `__call__` (the operation boundary, S-DDD
    logging rule 3); long-lived adapters/consumers hold it at module level.
    """
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
