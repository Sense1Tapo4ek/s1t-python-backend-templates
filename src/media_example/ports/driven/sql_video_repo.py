from dataclasses import dataclass
from uuid import UUID

import asyncpg

from shared.generics.errors import PortError

from ...app import IVideoRepo
from ...domain import Video
from .video_mappers import to_domain


@dataclass(slots=True, kw_only=True)
class SqlVideoRepo(IVideoRepo):
    _conn: asyncpg.Connection

    async def save(self, video: Video) -> None:
        try:
            await self._conn.execute(
                """
                INSERT INTO videos (id, source_key, status, uploaded_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status
                """,
                video.id,
                video.source_key,
                video.status.value,
                video.uploaded_at,
            )
        except asyncpg.PostgresError as exc:
            raise PortError(f"save video failed: {exc}") from exc

    async def get_by_id(self, video_id: UUID) -> Video | None:
        try:
            row = await self._conn.fetchrow(
                "SELECT * FROM videos WHERE id = $1",
                video_id,
            )
        except asyncpg.PostgresError as exc:
            raise PortError(f"get video by id failed: {exc}") from exc
        return to_domain(row) if row is not None else None

    async def list_recent(self, limit: int) -> list[Video]:
        try:
            rows = await self._conn.fetch(
                "SELECT * FROM videos ORDER BY uploaded_at DESC LIMIT $1",
                limit,
            )
        except asyncpg.PostgresError as exc:
            raise PortError(f"list recent videos failed: {exc}") from exc
        return [to_domain(r) for r in rows]
