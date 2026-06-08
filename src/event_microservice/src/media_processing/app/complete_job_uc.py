from dataclasses import dataclass
from uuid import UUID

import structlog

from ..domain import JobKind, JoinPolicy
from .interfaces import IJoinStore

_log = structlog.get_logger("media_processing.complete_job")


@dataclass(frozen=True, slots=True, kw_only=True)
class CompleteJobUC:
    _store: IJoinStore
    _fan_out: int

    async def __call__(self, video_id: UUID, kind: JobKind) -> None:
        done = await self._store.add(video_id, kind)
        if JoinPolicy.is_complete(done_count=done, fan_out=self._fan_out):
            # Phase C swaps this milestone log for publishing `video_processed`.
            _log.info("video processed", video_id=str(video_id), jobs_done=done)
            await self._store.clear(video_id)
