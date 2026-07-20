from dataclasses import dataclass
from uuid import uuid4

import msgspec
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.app import IClock
from shared.generics.errors import PortError

from ...app import IOutboxRepo
from ...domain import VideoUploaded
from .integration_events import VideoUploadedIntegration
from .orm_models import OutboxRow


@dataclass(slots=True, kw_only=True)
class SqlOutboxRepo(IOutboxRepo):
    _session: AsyncSession
    _clock: IClock

    async def add(self, event: VideoUploaded) -> None:
        integration = VideoUploadedIntegration(
            event_id=uuid4(),
            occurred_at=self._clock.now(),
            video_id=event.video_id,
            source_key=event.source_key,
            uploaded_at=event.uploaded_at,
        )
        payload = msgspec.json.encode(integration)
        try:
            self._session.add(
                OutboxRow(
                    id=integration.event_id, event_type=integration.event_type, payload=payload
                )
            )
            await self._session.flush()
        except SQLAlchemyError as exc:
            raise PortError(f"add outbox message failed: {exc}") from exc
