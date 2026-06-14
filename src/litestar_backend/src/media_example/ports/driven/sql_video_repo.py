from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, literal, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.generics.errors import PortError

from ...app import IVideoRepo
from ...domain import Video, VideoStatus
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
            .on_conflict_do_update(
                index_elements=["id"],
                set_={"status": video.status.value, "updated_at": func.now()},
            )
        )
        try:
            await self._session.execute(stmt)
        except SQLAlchemyError as exc:
            raise PortError(f"save video failed: {exc}") from exc

    async def get_by_id(self, video_id: UUID) -> Video | None:
        try:
            result = await self._session.execute(
                select(VideoRow).where(VideoRow.id == video_id, VideoRow.deleted_at.is_(None))
            )
        except SQLAlchemyError as exc:
            raise PortError(f"get video by id failed: {exc}") from exc
        row = result.scalar_one_or_none()
        return _to_domain(row) if row is not None else None

    async def list_page(self, after: tuple[datetime, UUID] | None, limit: int) -> list[Video]:
        stmt = (
            select(VideoRow)
            .where(VideoRow.deleted_at.is_(None))
            .order_by(VideoRow.uploaded_at.desc(), VideoRow.id.desc())
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(
                tuple_(VideoRow.uploaded_at, VideoRow.id)
                < tuple_(literal(after[0]), literal(after[1]))
            )
        try:
            result = await self._session.execute(stmt)
        except SQLAlchemyError as exc:
            raise PortError(f"list videos page failed: {exc}") from exc
        return [_to_domain(r) for r in result.scalars().all()]

    async def soft_delete(self, video_id: UUID) -> bool:
        stmt = (
            update(VideoRow)
            .where(VideoRow.id == video_id, VideoRow.deleted_at.is_(None))
            .values(deleted_at=func.now())
        )
        try:
            cursor: CursorResult = await self._session.execute(stmt)  # type: ignore[assignment]
        except SQLAlchemyError as exc:
            raise PortError(f"soft delete video failed: {exc}") from exc
        return cursor.rowcount > 0
