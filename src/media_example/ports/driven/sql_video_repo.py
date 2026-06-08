from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.generics.errors import PortError

from ...app import IVideoRepo
from ...domain import Video
from ...domain.video_status_vo import VideoStatus
from .orm_models import VideoRow


def _to_domain(row: VideoRow) -> Video:
    return Video.reconstitute(
        id=row.id,
        source_key=row.source_key,
        status=VideoStatus(row.status),
        uploaded_at=row.uploaded_at,
    )


@dataclass(slots=True, kw_only=True)
class SqlVideoRepo(IVideoRepo):
    _session: AsyncSession

    async def save(self, video: Video) -> None:
        stmt = (
            pg_insert(VideoRow)
            .values(
                id=video.id,
                source_key=video.source_key,
                status=video.status.value,
                uploaded_at=video.uploaded_at,
            )
            .on_conflict_do_update(index_elements=["id"], set_={"status": video.status.value})
        )
        try:
            await self._session.execute(stmt)
        except SQLAlchemyError as exc:
            raise PortError(f"save video failed: {exc}") from exc

    async def get_by_id(self, video_id: UUID) -> Video | None:
        try:
            result = await self._session.execute(select(VideoRow).where(VideoRow.id == video_id))
        except SQLAlchemyError as exc:
            raise PortError(f"get video by id failed: {exc}") from exc
        row = result.scalar_one_or_none()
        return _to_domain(row) if row is not None else None

    async def list_recent(self, limit: int) -> list[Video]:
        try:
            result = await self._session.execute(
                select(VideoRow).order_by(VideoRow.uploaded_at.desc()).limit(limit)
            )
        except SQLAlchemyError as exc:
            raise PortError(f"list recent videos failed: {exc}") from exc
        return [_to_domain(r) for r in result.scalars().all()]
