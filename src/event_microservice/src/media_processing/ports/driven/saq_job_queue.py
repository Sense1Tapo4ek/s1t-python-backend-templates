from dataclasses import dataclass
from uuid import UUID

from saq import Queue

from shared.generics.errors import PortError

from ...app import IJobQueue
from ...domain import JobKind


@dataclass(slots=True, kw_only=True)
class SaqJobQueue(IJobQueue):
    _queue: Queue
    _retries: int
    _timeout: int

    async def enqueue(self, video_id: UUID, kind: JobKind) -> None:
        try:
            await self._queue.enqueue(
                kind.value,
                video_id=str(video_id),
                retries=self._retries,
                timeout=self._timeout,
            )
        except Exception as exc:  # saq surfaces backend errors as bare exceptions
            raise PortError(f"enqueue {kind.value} failed for {video_id}: {exc}") from exc
