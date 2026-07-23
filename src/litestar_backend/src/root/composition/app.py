import secrets
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Any

from advanced_alchemy.exceptions import NotFoundError as AlchemyNotFoundError
from litestar import Litestar
from litestar.channels import ChannelsPlugin
from litestar.channels.backends.redis import RedisChannelsStreamBackend
from litestar.config.csrf import CSRFConfig
from litestar.connection import Request
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.datastructures import CacheControlHeader
from litestar.exceptions import (
    NotAuthorizedException,
    PermissionDeniedException,
)
from litestar.middleware import DefineMiddleware
from litestar.middleware.rate_limit import RateLimitConfig
from litestar.openapi import OpenAPIConfig
from litestar.openapi.spec import Contact, Server, Tag
from litestar.plugins.problem_details import (
    ProblemDetailsConfig,
    ProblemDetailsException,
    ProblemDetailsPlugin,
)
from litestar.plugins.prometheus import PrometheusConfig
from litestar.response import Response
from litestar.static_files import create_static_files_router
from litestar.stores.redis import RedisStore
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
from auth.adapters import AuthMiddleware
from auth.adapters.driving.api import ApiKeyController, TokenController, UserController
from auth.app import JwtDisabledError
from auth.ports.driving import SECURITY_COMPONENTS, require_role
from db_example_litestar.adapters.driving import AuthorController, BookController
from media_example import VIDEOS_CHANNEL
from media_example.adapters.driving import VideoController, VideoFeedController
from root.composition.lifespan import lifespan
from root.config import RootConfig
from shared.adapters.driven.valkey import build_valkey_client
from shared.adapters.metrics import build_prom_controller
from shared.adapters.middleware import (
    AccessLogMiddleware,
    SecurityHeadersMiddleware,
    TraceIdMiddleware,
)
from shared.adapters.problem_details import (
    app_to_problem,
    domain_to_problem,
    jwt_disabled_to_problem,
    not_found_to_problem,
    port_to_problem,
    problem_handler,
    unexpected_to_problem,
)
from shared.config import AppEnv, BaseAppConfig, MetricsConfig, ValkeyConfig
from shared.domain.auth import Role
from shared.generics.config import PROJECT_ROOT
from shared.generics.errors import AppError, DomainError, NotFoundError, PortError

_STATIC_DIR = PROJECT_ROOT / "static"


def _resolve_app_version() -> str:
    """Falls back to "0.0.0+unknown" when running from source without an
    installed dist."""
    try:
        return _pkg_version("litestar-base")
    except PackageNotFoundError:
        return "0.0.0+unknown"


# Litestar 2.23's ProblemDetailsPlugin maps exceptions via handlers that bypass
# `config.exception_handler`, dropping the request-side `instance` field. So we
# wrap these converters as app-level handlers through `problem_handler`, leaving
# the plugin only for `enable_for_all_http_exceptions` (framework HTTPExceptions).
EXCEPTION_TO_PROBLEM: dict[type[Exception], Callable[[Any], ProblemDetailsException]] = {
    DomainError: domain_to_problem,
    AppError: app_to_problem,
    JwtDisabledError: jwt_disabled_to_problem,
    NotFoundError: not_found_to_problem,
    AlchemyNotFoundError: not_found_to_problem,
    PortError: port_to_problem,
}


def _as_handler(
    convert: Callable[[Any], ProblemDetailsException],
) -> Callable[[Request[Any, Any, Any], Exception], Response[Any]]:
    def handler(request: Request[Any, Any, Any], exc: Exception) -> Response[Any]:
        return problem_handler(request, convert(exc))

    return handler


def _build_exception_handlers(*, is_dev: bool) -> dict[Any, Any]:
    handlers: dict[Any, Any] = {
        NotAuthorizedException: not_authorized_handler,
        PermissionDeniedException: permission_denied_handler,
    }
    for exc_type, convert in EXCEPTION_TO_PROBLEM.items():
        handlers[exc_type] = _as_handler(convert)
    if not is_dev:
        # PROD catch-all. In DEV, unhandled Exception -> Litestar debug renderer.
        handlers[Exception] = _as_handler(unexpected_to_problem)
    return handlers


def _build_plugins() -> list[Any]:
    return [
        ProblemDetailsPlugin(
            ProblemDetailsConfig(
                enable_for_all_http_exceptions=True,
                exception_handler=problem_handler,
            )
        ),
    ]


# Brute-force and unauthenticated-write surface. Safe methods and everything
# else stay un-throttled. Behind a reverse proxy configure real-IP forwarding
# (see RATE_LIMIT_PER_MINUTE in .env.full.example) or all clients share one
# bucket keyed on the proxy's address.
_THROTTLED_PATHS = frozenset(
    {"/auth/login", "/auth/register", "/auth/refresh", "/admin/login", "/videos"}
)


def _should_throttle(request: Request) -> bool:
    return request.method == "POST" and request.url.path in _THROTTLED_PATHS


def _build_rate_limit(config: RootConfig) -> RateLimitConfig:
    return RateLimitConfig(
        rate_limit=("minute", config.rate_limit_per_minute),
        check_throttle_handler=_should_throttle,
    )


def _build_csrf(config: RootConfig) -> CSRFConfig:
    secret = config.csrf_secret.get_secret_value() if config.csrf_secret else secrets.token_hex(32)
    # Enforced ONLY under /admin (the browser form surface). Every other path
    # is excluded: API clients authenticate per-request with bearer
    # credentials, and AuthMiddleware accepts the admin cookie only on the
    # admin surface (SameSite=Strict on top) -- cross-site forms can attach
    # no credential to the excluded paths.
    return CSRFConfig(secret=secret, exclude=["^/(?!admin)"])


def _build_middleware(config: RootConfig, prom_config: PrometheusConfig) -> list[Any]:
    return [
        # Outermost -- covers responses from inner middleware that short-circuit.
        DefineMiddleware(
            SecurityHeadersMiddleware,
            csp=config.security_csp,
            hsts_enabled=config.security_hsts_enabled,
        ),
        DefineMiddleware(TraceIdMiddleware),
        _build_rate_limit(config).middleware,
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
            "Groups: Health, the two db_example CRUD contexts (raw asyncpg "
            "vs advanced-alchemy), Admin Logs (file-tail viewer API), Metrics "
            "(Prometheus + custom by-name metrics), and Admin UI (server-rendered "
            "pages). The db_example_* and Metrics endpoints are illustrative "
            "examples meant to be deleted when adapting the template."
        ),
        use_handler_docstrings=True,
        contact=Contact(name="litestar-base maintainers"),
        servers=[Server(url="/", description="This deployment")],
        components=SECURITY_COMPONENTS,
        tags=[
            Tag(name="Health", description="Liveness/readiness probes and build info."),
            Tag(
                name="Auth",
                description="JWT token issuance, refresh rotation, and revocation. Bootstrap requires the admin credential.",
            ),
            Tag(
                name="db_example (Alchemy)",
                description="Example CRUD via SQLAlchemy 2.0 + advanced-alchemy. Illustrative; delete when adapting.",
            ),
            Tag(
                name="Admin Logs",
                description="JSON + SSE API backing the file-tail log viewer (admin role required).",
            ),
            Tag(
                name="Metrics",
                description="Prometheus scrape + a generic by-name custom-metrics demo. Illustrative.",
            ),
            Tag(
                name="Admin UI",
                description="Server-rendered HTML pages and auth redirects - not a JSON API.",
            ),
            Tag(
                name="media",
                description="Video ingest pipeline: upload (202 + outbox), list recent, live SSE feed. Golden example context.",
            ),
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
    prom_controller = build_prom_controller(metrics_cfg, guard=require_role(Role.ADMIN))

    valkey_cfg = ValkeyConfig()
    valkey_client = build_valkey_client(valkey_cfg.url)
    channels = ChannelsPlugin(
        backend=RedisChannelsStreamBackend(history=0, redis=valkey_client),
        channels=[VIDEOS_CHANNEL],
    )

    app = Litestar(
        route_handlers=[
            HealthController,
            LoginController,
            TokenController,
            ApiKeyController,
            UserController,
            AdminController,
            LogsPageController,
            LogsApiController,
            ExportController,
            AuthorController,
            BookController,
            VideoController,
            VideoFeedController,
            static_router,
            prom_controller,
        ],
        middleware=_build_middleware(config, prom_config),
        csrf_config=_build_csrf(config),
        # Rate-limit counters live in Valkey so the cap holds across workers.
        stores={"rate_limit": RedisStore(redis=valkey_client, namespace="rate_limit")},
        plugins=[*_build_plugins(), channels],
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
