from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Any

from advanced_alchemy.exceptions import NotFoundError as AlchemyNotFoundError
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
from litestar.openapi.spec import Contact, Server, Tag
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
from auth.adapters.middleware import AuthMiddleware
from db_example_litestar.adapters.driving import AuthorController, BookController
from db_example_sddd.adapters.driving import PerRequestItemController, PooledItemController
from db_example_sddd.app import ItemNotFound
from metrics.adapters.driving import MetricsDemoController, build_prom_controller
from metrics.config import MetricsConfig
from root.composition.lifespan import lifespan
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

_STATIC_DIR = PROJECT_ROOT / "static"


def _resolve_app_version() -> str:
    """Falls back to "0.0.0+unknown" when running from source without an
    installed dist."""
    try:
        return _pkg_version("litestar-base")
    except PackageNotFoundError:
        return "0.0.0+unknown"


def _http_exception_handler(_req: Request, exc: HTTPException) -> Response:
    """Generic 4xx fallback.

    Workaround for snitchbot's `install()`: it registers an Exception
    handler that re-raises HTTPException, which Litestar then renders as
    a bare 500 with no body. Without this catch-all, every
    ValidationException/NotFoundException/etc. degrades to an empty 500.
    """
    return Response(status_code=exc.status_code, content={"detail": exc.detail})


def _build_exception_handlers(*, is_dev: bool) -> dict[Any, Any]:
    # In DEV we want Litestar's debug renderer to surface the full traceback
    # to the client. Registering a catch-all Exception handler would short-
    # circuit that, so we only install it in PROD.
    handlers: dict[Any, Any] = {
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
        handlers[Exception] = fallback_500_handler
    return handlers


def _build_middleware(config: RootConfig, prom_config: PrometheusConfig) -> list[Any]:
    return [
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
    ]


def _build_openapi_config(app_name: str) -> OpenAPIConfig:
    return OpenAPIConfig(
        title=app_name,
        version=_resolve_app_version(),
        description=(
            "Litestar starter template (strict-DDD per bounded context). "
            "Groups: Health, the two db_example CRUD contexts (raw aiosqlite "
            "vs advanced-alchemy), Admin Logs (file-tail viewer API), Metrics "
            "(Prometheus + custom by-name metrics), and Admin UI (server-rendered "
            "pages). The db_example_* and Metrics endpoints are illustrative "
            "examples meant to be deleted when adapting the template."
        ),
        use_handler_docstrings=True,
        contact=Contact(name="litestar-base maintainers"),
        servers=[Server(url="/", description="This deployment")],
        tags=[
            Tag(name="Health", description="Liveness/readiness probes and build info."),
            Tag(name="db_example (SDDD)", description="Example CRUD over raw aiosqlite (pooled + per-request variants). Illustrative; delete when adapting."),
            Tag(name="db_example (Alchemy)", description="Example CRUD via SQLAlchemy 2.0 + advanced-alchemy. Illustrative; delete when adapting."),
            Tag(name="Admin Logs", description="JSON + SSE API backing the file-tail log viewer (admin role required)."),
            Tag(name="Metrics", description="Prometheus scrape + a generic by-name custom-metrics demo. Illustrative."),
            Tag(name="Admin UI", description="Server-rendered HTML pages and auth redirects - not a JSON API."),
        ],
    )


def build_app() -> Litestar:
    base_config = BaseAppConfig()
    metrics_cfg = MetricsConfig()
    config = RootConfig()
    is_dev = config.app_env == AppEnv.DEV

    # Single asset mount at the project's `static/` root. URL path mirrors
    # the on-disk path (`/static/admin/log/style.css` -> `static/admin/log/
    # style.css`). 1h browser cache; raise/lower per environment.
    static_router = create_static_files_router(
        path="/static",
        directories=[_STATIC_DIR],
        cache_control=CacheControlHeader(max_age=3600),
    )

    prom_config = PrometheusConfig(
        app_name=base_config.app_name,
        prefix=base_config.app_name.replace("-", "_"),
        group_path=True,
        buckets=list[str | float](metrics_cfg.http_buckets),
        exclude=[metrics_cfg.prom_endpoint_path],
    )
    prom_controller = build_prom_controller(metrics_cfg)

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
            MetricsDemoController,
            static_router,
            prom_controller,
        ],
        middleware=_build_middleware(config, prom_config),
        openapi_config=_build_openapi_config(config.app_name),
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
        exception_handlers=_build_exception_handlers(is_dev=is_dev),
    )
    install_snitchbot(app)
    return app
