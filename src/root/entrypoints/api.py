import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Any

import snitchbot
import structlog
from dishka.integrations.litestar import setup_dishka
from litestar import Litestar, Response
from litestar.channels import ChannelsPlugin
from litestar.channels.backends.memory import MemoryChannelsBackend
from litestar.connection import Request
from litestar.datastructures import CacheControlHeader
from litestar.exceptions import (
    HTTPException,
    NotAuthorizedException,
    PermissionDeniedException,
    ValidationException,
)
from litestar.middleware import DefineMiddleware
from litestar.openapi import OpenAPIConfig
from litestar.static_files import create_static_files_router
from snitchbot.integrations.litestar import install as install_snitchbot

from admin.adapters.driving.api import AdminController, HealthController, LoginController
from admin.adapters.driving.error_handlers import (
    not_authorized_handler,
    permission_denied_handler,
)
from admin.log.adapters.driving.api import (
    ExportController,
    LogsApiController,
    LogsPageController,
)
from admin.log.adapters.driving.error_handlers import (
    dsl_syntax_handler,
    invalid_log_filter_handler,
)
from admin.log.adapters.lifespan import LogLifespanManager
from admin.log.config import AdminLogConfig
from admin.log.domain import DslSyntaxError, InvalidLogFilterError
from auth.adapters.middleware import AuthMiddleware
from auth.ports.driving import AuthFacade
from root.composition.container import build_container
from root.config import RootConfig
from shared.adapters.error_handlers import (
    adapter_error_handler,
    app_error_handler,
    domain_error_handler,
    fallback_500_handler,
    port_error_handler,
    validation_exception_handler,
)
from shared.adapters.middleware import (
    AccessLogMiddleware,
    SecurityHeadersMiddleware,
    TraceIdMiddleware,
)
from shared.app import IEventBus
from shared.config import AppEnv
from shared.generics.errors import AdapterError, AppError, DomainError, PortError
from shared.logging import configure_structlog


def _build_channels_plugin(log_config: AdminLogConfig) -> ChannelsPlugin:
    """Single ChannelsPlugin shared by Litestar (transport) and DI (publishers).

    `dropleft` strategy: when a slow SSE consumer's queue fills up, oldest
    messages are dropped silently. Critical for the log broadcast channel —
    we never want a stuck client to back-pressure the sink writer.

    `arbitrary_channels_allowed=True`: domain events use dynamic channel
    names derived from event class FQN (`event:ordering.domain.events...`),
    so we cannot enumerate them upfront.
    """
    return ChannelsPlugin(
        backend=MemoryChannelsBackend(),
        arbitrary_channels_allowed=True,
        subscriber_max_backlog=log_config.log_sse_queue_size,
        subscriber_backlog_strategy="dropleft",
    )


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncIterator[None]:
    started = time.perf_counter()

    config = RootConfig()
    snitchbot.init(service=config.app_name)

    container = build_container(channels_plugin=app.state.channels_plugin)
    app.state.container = container
    setup_dishka(container=container, app=app)

    queue = await container.get(asyncio.Queue[str])
    configure_structlog(queue, app_name=config.app_name)

    log = structlog.get_logger("root.lifespan")
    log.info("lifespan starting", service=config.app_name, queue_maxsize=queue.maxsize)
    log.info("container ready")

    event_bus = await container.get(IEventBus)
    # Register domain event handlers here before bus.start();
    # see docs/subsystems/event_bus.md for the pattern.
    await event_bus.start()

    # Resolve middleware-bound facades once at startup. ASGI middleware runs
    # outside the Dishka request scope, so reading from app.state per request
    # is cheaper and clearer than walking the container each time.
    app.state.auth_facade = await container.get(AuthFacade)

    manager: LogLifespanManager | None = None
    try:
        manager = await container.get(LogLifespanManager)
        log.info("log subsystem starting")
        await manager.start()
        log.info(
            "lifespan started",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
    except Exception:
        log.exception("lifespan_start_failed")
        raise

    try:
        yield
    finally:
        log.info("lifespan stopping")
        stop_started = time.perf_counter()
        try:
            if manager is not None:
                await manager.stop()
                log.info("log subsystem stopped")
        except Exception:
            log.exception("lifespan_stop_failed")
        try:
            await event_bus.stop()
        except Exception:
            log.exception("event_bus_stop_failed")
        await container.close()
        log.info(
            "lifespan stopped",
            duration_ms=round((time.perf_counter() - stop_started) * 1000, 2),
        )


def _http_exception_handler(_req: Request, exc: HTTPException) -> Response:
    """Generic 4xx fallback.

    Workaround for snitchbot's `install()`: it registers an Exception
    handler that re-raises HTTPException, which Litestar then renders as
    a bare 500 with no body. Without this catch-all, every
    ValidationException/NotFoundException/etc. degrades to an empty 500.
    """
    return Response(status_code=exc.status_code, content={"detail": exc.detail})


def _resolve_app_version() -> str:
    """Falls back to "0.0.0+unknown" when running from source without an
    installed dist."""
    try:
        return _pkg_version("litestar-base")
    except PackageNotFoundError:
        return "0.0.0+unknown"


def create_app() -> Litestar:
    log_config = AdminLogConfig()
    static_router = create_static_files_router(
        path="/admin/logs/static",
        directories=[log_config.log_static_path],
        # 1 hour browser cache. The dashboard assets are versioned by
        # deployment cadence; raise/lower per environment if you ship
        # frontend updates more aggressively.
        cache_control=CacheControlHeader(max_age=3600),
    )

    channels_plugin = _build_channels_plugin(log_config)
    config = RootConfig()
    is_dev = config.app_env == AppEnv.DEV

    # In DEV we want Litestar's debug renderer to surface the full traceback
    # to the client. Registering a catch-all Exception handler would short-
    # circuit that, so we only install it in PROD.
    exception_handlers: dict[Any, Any] = {
        DslSyntaxError: dsl_syntax_handler,
        InvalidLogFilterError: invalid_log_filter_handler,
        NotAuthorizedException: not_authorized_handler,
        PermissionDeniedException: permission_denied_handler,
        # ValidationException must be registered ahead of HTTPException so
        # Litestar picks the specialised handler that retains `.extra`.
        ValidationException: validation_exception_handler,
        HTTPException: _http_exception_handler,
        DomainError: domain_error_handler,
        AppError: app_error_handler,
        PortError: port_error_handler,
        AdapterError: adapter_error_handler,
    }
    if not is_dev:
        exception_handlers[Exception] = fallback_500_handler

    app = Litestar(
        route_handlers=[
            HealthController,
            LoginController,
            AdminController,
            LogsPageController,
            LogsApiController,
            ExportController,
            static_router,
        ],
        middleware=[
            # Outermost — covers responses from inner middleware that short-circuit.
            DefineMiddleware(
                SecurityHeadersMiddleware,
                csp=config.security_csp,
                hsts_enabled=config.security_hsts_enabled,
            ),
            DefineMiddleware(TraceIdMiddleware),
            DefineMiddleware(AuthMiddleware),
            DefineMiddleware(AccessLogMiddleware),
        ],
        plugins=[channels_plugin],
        openapi_config=OpenAPIConfig(
            title=config.app_name,
            version=_resolve_app_version(),
        ),
        lifespan=[lifespan],
        # Bound to APP_ENV — a stray LITESTAR_DEBUG=1 in prod is ignored.
        debug=is_dev,
        exception_handlers=exception_handlers,
    )
    app.state.channels_plugin = channels_plugin
    install_snitchbot(app)
    return app
