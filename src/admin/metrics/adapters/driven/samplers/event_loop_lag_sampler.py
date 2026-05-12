"""Samples event loop scheduling latency.

Algorithm: schedule a coroutine to wake every `_interval_s`. The
difference between the requested wake time and the actual one is the
"lag" — time the event loop took before getting to us. p95 over the
last `_window` samples is a robust indicator of whether the loop is
healthy (~ low ms) or contended (tens of ms+).

Background task is owned by this object; start()/stop() are
lifespan-driven.
"""

import asyncio
import contextlib
from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True, kw_only=True)
class EventLoopLagSampler:
    _interval_s: float
    _window: int
    _samples: deque[float] = field(init=False)
    _task: asyncio.Task[None] | None = field(default=None, init=False)
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    def __post_init__(self) -> None:
        self._samples = deque(maxlen=self._window)

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="metrics-loop-lag")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        task = self._task
        self._task = None
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await asyncio.wait_for(task, timeout=2.0)

    def current_p95_ms(self) -> float:
        if not self._samples:
            return 0.0
        ordered = sorted(self._samples)
        idx = max(0, int(len(ordered) * 0.95) - 1)
        return ordered[idx] * 1000.0

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        while not self._stop_event.is_set():
            expected = loop.time() + self._interval_s
            try:
                await asyncio.sleep(self._interval_s)
            except asyncio.CancelledError:
                return
            actual = loop.time()
            self._samples.append(max(0.0, actual - expected))
