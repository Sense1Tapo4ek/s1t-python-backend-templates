import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import snitchbot
import structlog
from dishka.integrations.litestar import setup_dishka
from litestar import Litestar
from litestar.channels import ChannelsPlugin

from admin.log.config import AdminLogConfig
from auth.ports.driving import AuthFacade
from db_example_litestar.adapters.lifespan_manager import (
    DbExampleLitestarLifespanManager,
)
from media_example.adapters.lifespan_manager import MediaLifespanManager
from root.composition.container import build_container
from root.config import RootConfig
from shared.logging import configure_structlog


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncIterator[None]:
    started = time.perf_counter()

    config = RootConfig()
    snitchbot.init(service=config.app_name)

    container = build_container(channels=app.plugins.get(ChannelsPlugin))
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

    alchemy_manager: DbExampleLitestarLifespanManager | None = None
    media_manager: MediaLifespanManager | None = None
    try:
        alchemy_manager = await container.get(DbExampleLitestarLifespanManager)
        log.info("db_example_litestar starting")
        await alchemy_manager.start()

        media_manager = await container.get(MediaLifespanManager)
        log.info("media_example starting")
        # ChannelsPlugin enters its own lifespan AFTER this one (plugins append
        # to the list), so a status event consumed in the first milliseconds may
        # find the channel queue not yet started. The feed publish is best-effort
        # (_publish_best_effort swallows PortError), so this window only costs a
        # live browser push -- do not "fix" the swallow into a propagate.
        await media_manager.start()
        log.info("media_example started")

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
            if media_manager is not None:
                await media_manager.stop()
                log.info("media_example stopped")
        except Exception:
            log.exception("media_example_stop_failed")
        await container.close()
        log.info(
            "lifespan stopped",
            duration_ms=round((time.perf_counter() - stop_started) * 1000, 2),
        )
