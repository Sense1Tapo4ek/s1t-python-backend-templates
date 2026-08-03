from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.app import IClock
from shared.generics.errors import PortError

from ...app import IIdempotencyStore, StoredUpload
from ...domain import Video, VideoStatus
from .orm_models import IdempotencyRow


def _snapshot(video: Video) -> dict[str, Any]:
    return {
        "id": str(video.id),
        "source_key": video.source_key,
        "status": video.status.value,
        "uploaded_at": video.uploaded_at.isoformat(),
        "document": video.document,
    }


def _restore(snapshot: dict[str, Any]) -> Video:
    return Video.reconstitute(
        id=UUID(snapshot["id"]),
        source_key=snapshot["source_key"],
        status=VideoStatus(snapshot["status"]),
        uploaded_at=datetime.fromisoformat(snapshot["uploaded_at"]),
        document=snapshot["document"],
    )


@dataclass(slots=True, kw_only=True)
class SqlIdempotencyStore(IIdempotencyStore):
    _session: AsyncSession
    _clock: IClock
    _ttl_seconds: int

    async def claim(self, key: str, *, fingerprint: str, video: Video) -> bool:
        # ON CONFLICT DO NOTHING is the claim: exactly one transaction gets a
        # row back. A concurrent claim of the same key waits here on the
        # primary-key index until the first transaction commits or rolls back.
        stmt = (
            pg_insert(IdempotencyRow)
            .values(
                key=key,
                fingerprint=fingerprint,
                response=_snapshot(video),
                expires_at=self._clock.now() + timedelta(seconds=self._ttl_seconds),
            )
            .on_conflict_do_nothing(index_elements=["key"])
            .returning(IdempotencyRow.key)
        )
        try:
            result = await self._session.execute(stmt)
        except SQLAlchemyError as exc:
            raise PortError(f"claim idempotency key failed: {exc}") from exc
        return result.scalar_one_or_none() is not None

    async def find(self, key: str) -> StoredUpload | None:
        try:
            result = await self._session.execute(
                select(IdempotencyRow).where(IdempotencyRow.key == key)
            )
        except SQLAlchemyError as exc:
            raise PortError(f"find idempotency key failed: {exc}") from exc
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return StoredUpload(fingerprint=row.fingerprint, video=_restore(row.response))
