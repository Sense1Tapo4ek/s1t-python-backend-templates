import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import snitchbot
import structlog
from dishka.integrations.litestar import setup_dishka
from litestar import Litestar

from admin.log.config import AdminLogConfig
from auth.ports.driving import AuthFacade
from db_example_litestar.adapters.db_example_litestar_lifespan_manager import (
    DbExampleLitestarLifespanManager,
)
from metrics.adapters import MetricsLifespanManager
from orders.adapters.orders_lifespan_manager import OrdersLifespanManager
from root.composition.container import build_container
from root.config import RootConfig
from shared.logging import configure_structlog


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncIterator[None]:
    started = time.perf_counter()

    config = RootConfig()
    snitchbot.init(service=config.app_name)

    container = build_container(app)
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
    alchemy_manager: DbExampleLitestarLifespanManager | None = None
    orders_manager: OrdersLifespanManager | None = None
    try:
        metrics_manager = await container.get(MetricsLifespanManager)
        log.info("metrics subsystem starting")
        await metrics_manager.start()

        alchemy_manager = await container.get(DbExampleLitestarLifespanManager)
        log.info("db_example_litestar starting")
        await alchemy_manager.start()

        orders_manager = await container.get(OrdersLifespanManager)
        log.info("orders starting")
        await orders_manager.start()

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
            if orders_manager is not None:
                await orders_manager.stop()
                log.info("orders stopped")
        except Exception:
            log.exception("orders_stop_failed")
        try:
            if alchemy_manager is not None:
                await alchemy_manager.stop()
                log.info("db_example_litestar stopped")
        except Exception:
            log.exception("db_example_litestar_stop_failed")
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
