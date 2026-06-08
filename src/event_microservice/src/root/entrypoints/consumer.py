from faststream import FastStream
from faststream.redis import RedisBroker

from media_processing.adapters.driving import router
from media_processing.ports.driving import MediaProcessingFacade
from root.composition.container import build_container
from root.config import RootConfig
from shared.logging import configure_logging


def build_app() -> FastStream:
    configure_logging()
    config = RootConfig()
    broker = RedisBroker(config.valkey_url)
    broker.include_router(router)
    app = FastStream(broker)
    container = build_container()

    @app.on_startup
    async def _startup() -> None:
        facade = await container.get(MediaProcessingFacade)
        app.context.set_global("facade", facade)

    @app.on_shutdown
    async def _shutdown() -> None:
        await container.close()

    return app


app = build_app()
