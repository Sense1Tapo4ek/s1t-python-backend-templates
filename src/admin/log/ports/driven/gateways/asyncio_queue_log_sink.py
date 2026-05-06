import asyncio
from dataclasses import dataclass

from ....app.interfaces import ILogSink


@dataclass(slots=True, kw_only=True)
class AsyncioQueueLogSink(ILogSink):
    _queue: asyncio.Queue[str]

    async def put(self, raw_json: str) -> None:
        await self._queue.put(raw_json)
