from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from shared.domain.auth import Role
from shared.generics.errors import PortError

from ...domain import ApiKeyRecord
from .orm_models import ApiKeyRow, to_record


@dataclass(slots=True, kw_only=True)
class SqlApiKeyRepo:
    _sessionmaker: async_sessionmaker

    async def find_active_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        try:
            async with self._sessionmaker() as session:
                result = await session.execute(
                    select(ApiKeyRow).where(
                        ApiKeyRow.key_hash == key_hash, ApiKeyRow.deleted_at.is_(None)
                    )
                )
                row = result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise PortError(f"find api key by hash failed: {exc}") from exc
        return to_record(row) if row is not None else None

    async def create(self, *, key_hash: str, name: str, role: Role) -> UUID:
        api_key_id = uuid4()
        row = ApiKeyRow(id=api_key_id, key_hash=key_hash, name=name, role=role.value)
        try:
            async with self._sessionmaker() as session, session.begin():
                session.add(row)
        except SQLAlchemyError as exc:
            raise PortError(f"create api key failed: {exc}") from exc
        return api_key_id

    async def list_active(self) -> list[ApiKeyRecord]:
        try:
            async with self._sessionmaker() as session:
                result = await session.execute(
                    select(ApiKeyRow)
                    .where(ApiKeyRow.deleted_at.is_(None))
                    .order_by(ApiKeyRow.created_at.desc())
                )
                rows = result.scalars().all()
        except SQLAlchemyError as exc:
            raise PortError(f"list api keys failed: {exc}") from exc
        return [to_record(r) for r in rows]

    async def soft_delete(self, api_key_id: UUID) -> bool:
        try:
            async with self._sessionmaker() as session, session.begin():
                cursor: CursorResult = await session.execute(
                    update(ApiKeyRow)
                    .where(ApiKeyRow.id == api_key_id, ApiKeyRow.deleted_at.is_(None))
                    .values(deleted_at=func.now())
                )
        except SQLAlchemyError as exc:
            raise PortError(f"soft delete api key failed: {exc}") from exc
        return cursor.rowcount > 0
