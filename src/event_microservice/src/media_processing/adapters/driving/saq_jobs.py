import asyncio
from typing import Any
from uuid import UUID

from ...domain import JobKind
from ..driven.executors import plagiarism_blocking, transcode_cpu


async def stt(ctx: dict[str, Any], *, video_id: str) -> None:
    """Async / I/O-bound: await an external STT API (stand-in: asyncio.sleep)."""
    config = ctx["config"]
    await asyncio.sleep(config.fake_work_seconds)
    await ctx["facade"].complete_job(UUID(video_id), JobKind.STT)


async def plagiarism(ctx: dict[str, Any], *, video_id: str) -> None:
    """Thread pool: a blocking / GIL-releasing call run off the event loop."""
    config = ctx["config"]
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        ctx["thread_pool"], plagiarism_blocking, video_id, config.fake_work_seconds
    )
    await ctx["facade"].complete_job(UUID(video_id), JobKind.PLAGIARISM)


async def transcode(ctx: dict[str, Any], *, video_id: str) -> None:
    """Process pool: a CPU-bound loop run past the GIL in a separate process."""
    config = ctx["config"]
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        ctx["process_pool"], transcode_cpu, video_id, config.transcode_iterations
    )
    await ctx["facade"].complete_job(UUID(video_id), JobKind.TRANSCODE)
