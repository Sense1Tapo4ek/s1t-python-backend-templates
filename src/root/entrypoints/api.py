import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Any

import snitchbot
import structlog
from advanced_alchemy.exceptions import NotFoundError as AlchemyNotFoundError
from dishka.integrations.litestar import setup_dishka
from litestar import Litestar, Response
from litestar.connection import Request
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.datastructures import CacheControlHeader
from litestar.exceptions import (
    HTTPException,
    NotAuthorizedException,
    PermissionDeniedException,
    ValidationException,
)
from litestar.middleware import DefineMiddleware
from litestar.openapi import OpenAPIConfig
from litestar.plugins.prometheus import PrometheusConfig
from litestar.static_files import create_static_files_router
from litestar.template.config import TemplateConfig
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
from admin.log.config import AdminLogConfig
from admin.metrics.adapters.driving.api import build_prom_controller
from admin.metrics.adapters.lifespan import MetricsLifespanManager
from admin.metrics.config import MetricsConfig
from auth.adapters.middleware import AuthMiddleware
from auth.ports.driving import AuthFacade
from db_example_litestar.adapters.db_example_litestar_lifespan_manager import (
    DbExampleLitestarLifespanManager,
)
from db_example_litestar.adapters.driving import AuthorController, BookController
from db_example_sddd.adapters.db_example_sddd_lifespan_manager import (
    DbExampleSdddLifespanManager,
)
from db_example_sddd.adapters.driving import PerRequestItemController, PooledItemController
from db_example_sddd.app import ItemNotFound
from root.composition.container import build_container
from root.config import RootConfig
from shared.adapters.error_handlers import (
    adapter_error_handler,
    app_error_handler,
    domain_error_handler,
    fallback_500_handler,
    not_found_handler,
    port_error_handler,
    validation_exception_handler,
)
from shared.adapters.middleware import (
    AccessLogMiddleware,
    SecurityHeadersMiddleware,
    TraceIdMiddleware,
)
from shared.config import AppEnv, BaseAppConfig
from shared.generics.config import PROJECT_ROOT
from shared.generics.errors import AdapterError, AppError, DomainError, PortError
from shared.logging import configure_structlog

_STATIC_DIR = PROJECT_ROOT / "static"


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncIterator[None]:
    started = time.perf_counter()

    config = RootConfig()
    snitchbot.init(service=config.app_name)

    container = build_container()
    app.state.container = container
    setup_dishka(container=container, app=app)

    log_config = AdminLogConfig()
    if log_config.file_path is None:
        raise RuntimeError("LOG_FILE_PATH could not be resolved")
    configure_structlog(
        app_name=config.app_name,
        log_file_path=log_config.file_path,
        max_line_bytes=log_config.max_line_bytes,
    )

    log = structlog.get_logger("root.lifespan")
    log.info("lifespan starting", service=config.app_name)
    log.info("container ready")

    # Resolve middleware-bound facades once at startup. ASGI middleware runs
    # outside the Dishka request scope, so reading from app.state per request
    # is cheaper and clearer than walking the container each time.
    app.state.auth_facade = await container.get(AuthFacade)

    metrics_manager: MetricsLifespanManager | None = None
    db_manager: DbExampleSdddLifespanManager | None = None
    alchemy_manager: DbExampleLitestarLifespanManager | None = None
    try:
        metrics_manager = await container.get(MetricsLifespanManager)
        log.info("metrics subsystem starting")
        await metrics_manager.start()

        db_manager = await container.get(DbExampleSdddLifespanManager)
        log.info("db_example_sddd starting")
        await db_manager.start()

        alchemy_manager = await container.get(DbExampleLitestarLifespanManager)
        log.info("db_example_litestar starting")
        await alchemy_manager.start()

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
            if alchemy_manager is not None:
                await alchemy_manager.stop()
                log.info("db_example_litestar stopped")
        except Exception:
            log.exception("db_example_litestar_stop_failed")
        try:
            if db_manager is not None:
                await db_manager.stop()
                log.info("db_example_sddd stopped")
        except Exception:
            log.exception("db_example_sddd_stop_failed")
        try:
            if metrics_manager is not None:
                await metrics_manager.stop()
                log.info("metrics subsystem stopped")
        except Exception:
            log.exception("metrics_lifespan_stop_failed")
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
    base_config = BaseAppConfig()
    metrics_cfg = MetricsConfig()
    # Single asset mount at the project's `static/` root. URL path mirrors
    # the on-disk path (`/static/admin/log/style.css` -> `static/admin/log/
    # style.css`). 1h browser cache; raise/lower per environment.
    static_router = create_static_files_router(
        path="/static",
        directories=[_STATIC_DIR],
        cache_control=CacheControlHeader(max_age=3600),
    )

    config = RootConfig()
    is_dev = config.app_env == AppEnv.DEV

    prom_config = PrometheusConfig(
        app_name=base_config.app_name,
        prefix=base_config.app_name.replace("-", "_"),
        group_path=True,
        buckets=list[str | float](metrics_cfg.http_buckets),
        exclude=[metrics_cfg.prom_endpoint_path],
    )
    prom_controller = build_prom_controller(metrics_cfg)

    extra_handlers: list = [prom_controller]

    # In DEV we want Litestar's debug renderer to surface the full traceback
    # to the client. Registering a catch-all Exception handler would short-
    # circuit that, so we only install it in PROD.
    exception_handlers: dict[Any, Any] = {
        NotAuthorizedException: not_authorized_handler,
        PermissionDeniedException: permission_denied_handler,
        # ValidationException must be registered ahead of HTTPException so
        # Litestar picks the specialised handler that retains `.extra`.
        ValidationException: validation_exception_handler,
        HTTPException: _http_exception_handler,
        DomainError: domain_error_handler,
        AppError: app_error_handler,
        # Specific lookup-miss exceptions -> 404 (more specific than AppError 422).
        ItemNotFound: not_found_handler,
        AlchemyNotFoundError: not_found_handler,
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
            PooledItemController,
            PerRequestItemController,
            AuthorController,
            BookController,
            static_router,
            *extra_handlers,
        ],
        middleware=[
            # Outermost -- covers responses from inner middleware that short-circuit.
            DefineMiddleware(
                SecurityHeadersMiddleware,
                csp=config.security_csp,
                hsts_enabled=config.security_hsts_enabled,
            ),
            DefineMiddleware(TraceIdMiddleware),
            DefineMiddleware(AuthMiddleware),
            DefineMiddleware(AccessLogMiddleware),
            prom_config.middleware,
        ],
        openapi_config=OpenAPIConfig(
            title=config.app_name,
            version=_resolve_app_version(),
        ),
        # Single Jinja engine bound to the project's static/ root. Templates
        # are referenced by their path under static/ (e.g. "shared/_base.html",
        # "admin/dashboard.html"). Same directory the static router serves.
        template_config=TemplateConfig(
            directory=_STATIC_DIR,
            engine=JinjaTemplateEngine,
        ),
        lifespan=[lifespan],
        # Bound to APP_ENV -- a stray LITESTAR_DEBUG=1 in prod is ignored.
        debug=is_dev,
        exception_handlers=exception_handlers,
    )
    install_snitchbot(app)
    return app
