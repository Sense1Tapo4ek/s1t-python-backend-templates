from typing import Any
from uuid import UUID

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
    if exc is None:
        return
    job = ctx.get("job")
    _log.error("job failed", job=getattr(job, "function", None), exc_info=exc)
    if job is None or job.attempts < job.retries:
        return  # SAQ will retry; not terminal yet
    video_id = UUID(job.kwargs["video_id"])
    # AT-MOST-ONCE: after_process is not retried; a missed failed-event is
    # cheaper than blocking the worker, and the join TTL bounds the orphan.
    try:
        await ctx["facade"].on_job_failed(video_id)
    except Exception:
        _log.exception("on_job_failed hook failed", video_id=str(video_id))


settings: dict[str, Any] = {
    "queue": build_queue(RootConfig().valkey_url),
    "functions": [stt, plagiarism, transcode],
    "concurrency": _config.worker_concurrency,
    "startup": startup,
    "shutdown": shutdown,
    "after_process": after_process,
}
