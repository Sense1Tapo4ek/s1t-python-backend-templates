from faststream import FastStream
from faststream.redis import RedisBroker

from root.config import RootConfig
from shared.logging import configure_logging


def build_app() -> FastStream:
    configure_logging()
    config = RootConfig()
    broker = RedisBroker(config.valkey_url)
    # Slice 2 registers the `video_uploaded` stream subscriber on `broker` here.
    return FastStream(broker)


app = build_app()
