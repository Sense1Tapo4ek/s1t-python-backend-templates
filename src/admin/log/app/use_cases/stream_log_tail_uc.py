from collections.abc import AsyncGenerator
from dataclasses import dataclass

from ...app.interfaces import ILogReader
from ...domain import LogEntryEnt, LogFilterVo


@dataclass(frozen=True, slots=True, kw_only=True)
class StreamLogTailUc:
    """Yields log entries forever as they arrive.

    Backed by `ILogReader.stream_after`, which subscribes to the broadcast
    channel before draining the catch-up tail to avoid the race window
    where new entries land between the two reads. Caller must wrap the
    consumer in cancellation handling.
    """

    _reader: ILogReader

    async def __call__(
        self,
        filter_vo: LogFilterVo | None = None,
    ) -> AsyncGenerator[LogEntryEnt, None]:
        async for entry in self._reader.stream_after(cursor=None, filter_vo=filter_vo):
            yield entry
