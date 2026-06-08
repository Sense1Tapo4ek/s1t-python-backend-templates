import asyncio
from typing import Any
from uuid import UUID

from ...domain import JobKind
from ..driven.executors import plagiarism_blocking, transcode_cpu
from ..driven.metrics import JOB_DURATION, JOBS_PROCESSED


async def stt(ctx: dict[str, Any], *, video_id: str) -> None:
    """I/O-bound: awaits the external STT API; no executor needed."""
    config = ctx["config"]
    with JOB_DURATION.labels(kind=JobKind.STT.value).time():
        await asyncio.sleep(config.fake_work_seconds)
    await ctx["facade"].complete_job(UUID(video_id), JobKind.STT)
    JOBS_PROCESSED.labels(kind=JobKind.STT.value).inc()


async def plagiarism(ctx: dict[str, Any], *, video_id: str) -> None:
    """Thread pool: a blocking call that cannot be awaited, dispatched off the event loop."""
    config = ctx["config"]
    loop = asyncio.get_running_loop()
    with JOB_DURATION.labels(kind=JobKind.PLAGIARISM.value).time():
        await loop.run_in_executor(
            ctx["thread_pool"], plagiarism_blocking, video_id, config.fake_work_seconds
        )
    await ctx["facade"].complete_job(UUID(video_id), JobKind.PLAGIARISM)
    JOBS_PROCESSED.labels(kind=JobKind.PLAGIARISM.value).inc()


async def transcode(ctx: dict[str, Any], *, video_id: str) -> None:
    """Process pool: a CPU-bound loop run past the GIL in a separate process."""
    config = ctx["config"]
    loop = asyncio.get_running_loop()
    with JOB_DURATION.labels(kind=JobKind.TRANSCODE.value).time():
        await loop.run_in_executor(
            ctx["process_pool"], transcode_cpu, video_id, config.transcode_iterations
        )
    await ctx["facade"].complete_job(UUID(video_id), JobKind.TRANSCODE)
    JOBS_PROCESSED.labels(kind=JobKind.TRANSCODE.value).inc()
