from typing import Any

import structlog

from media_processing.adapters.driven.executors import build_process_pool, build_thread_pool
from media_processing.adapters.driven.metrics import start_metrics_server
from media_processing.adapters.driven.saq_setup import build_queue
from media_processing.adapters.driving import plagiarism, stt, transcode
from media_processing.config import MediaProcessingConfig
from media_processing.ports.driving import MediaProcessingFacade
from root.composition.container import build_container
from root.config import RootConfig
from shared.logging import configure_logging

_log = structlog.get_logger("event_microservice.saq_worker")
_config = MediaProcessingConfig()


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    start_metrics_server(_config.metrics_port)
    container = build_container()
    ctx["container"] = container
    ctx["config"] = _config
    ctx["facade"] = await container.get(MediaProcessingFacade)
    ctx["thread_pool"] = build_thread_pool(_config.thread_pool_size)
    ctx["process_pool"] = build_process_pool(_config.process_pool_size)


async def shutdown(ctx: dict[str, Any]) -> None:
    if "thread_pool" in ctx:
        ctx["thread_pool"].shutdown(wait=True)
    if "process_pool" in ctx:
        ctx["process_pool"].shutdown(wait=True)
    if "container" in ctx:
        await ctx["container"].close()


async def after_process(ctx: dict[str, Any]) -> None:
    exc = ctx.get("exception")
    if exc is not None:
        job = ctx.get("job")
        _log.error("job failed", job=getattr(job, "function", None), exc_info=exc)


settings: dict[str, Any] = {
    "queue": build_queue(RootConfig().valkey_url),
    "functions": [stt, plagiarism, transcode],
    "concurrency": _config.worker_concurrency,
    "startup": startup,
    "shutdown": shutdown,
    "after_process": after_process,
}
