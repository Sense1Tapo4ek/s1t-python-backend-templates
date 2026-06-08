from typing import Any

from saq import Queue

from root.composition.container import build_container
from root.config import RootConfig

from ...config import MediaProcessingConfig
from ...ports.driving import MediaProcessingFacade
from .executors import build_process_pool, build_thread_pool


def build_queue() -> Queue:
    return Queue.from_url(RootConfig().valkey_url)


async def startup(ctx: dict[str, Any]) -> None:
    config = MediaProcessingConfig()
    container = build_container()
    ctx["container"] = container
    ctx["config"] = config
    ctx["facade"] = await container.get(MediaProcessingFacade)
    ctx["thread_pool"] = build_thread_pool(config.thread_pool_size)
    ctx["process_pool"] = build_process_pool(config.process_pool_size)


async def shutdown(ctx: dict[str, Any]) -> None:
    if "thread_pool" in ctx:
        ctx["thread_pool"].shutdown(wait=True)
    if "process_pool" in ctx:
        ctx["process_pool"].shutdown(wait=True)
    if "container" in ctx:
        await ctx["container"].close()
