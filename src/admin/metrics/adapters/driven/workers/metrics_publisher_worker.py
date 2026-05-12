"""Periodic ticker that invokes PublishWorkerSnapshotUc.

The worker is the single owner of cadence — every other component is
either pull-based or driven by this tick. Errors during the use case
are logged and swallowed: metrics MUST NEVER take the process down.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import structlog

_log = structlog.get_logger(__name__)

_AsyncTick = Callable[[], Awaitable[None]]


@dataclass(slots=True, kw_only=True)
class MetricsPublisherWorker:
    _use_case: _AsyncTick
    _interval_s: float
    _task: asyncio.Task[None] | None = field(default=None, init=False)
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="metrics-publisher")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        task = self._task
        self._task = None
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await asyncio.wait_for(task, timeout=self._interval_s * 2 + 1.0)

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._use_case()
            except Exception as exc:
                _log.warning(
                    "metrics tick failed", error_type=type(exc).__name__
                )
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._interval_s
                )
                return
            except TimeoutError:
                continue
