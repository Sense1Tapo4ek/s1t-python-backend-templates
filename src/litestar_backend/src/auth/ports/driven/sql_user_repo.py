from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

import msgspec
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from shared.adapters.driven.postgres import keyset_older_than
from shared.app import IClock
from shared.domain.auth import Role
from shared.generics.errors import PortError

from ...domain import EmailTakenError, UserRecord
from .integration_events import UserRegisteredIntegration
from .orm_models import OutboxRow, UserRow, to_user_record


@dataclass(slots=True, kw_only=True)
class SqlUserRepo:
    _sessionmaker: async_sessionmaker
    _clock: IClock

    async def register(self, *, email: str, password_hash: str, role: Role) -> UserRecord:
        user_id = uuid4()
        event = UserRegisteredIntegration(
            event_id=uuid4(),
            occurred_at=self._clock.now(),
            user_id=user_id,
            role=role.value,
        )
        row = UserRow(id=user_id, email=email, password_hash=password_hash, role=role.value)
        try:
            async with self._sessionmaker() as session, session.begin():
                session.add(row)
                session.add(
                    OutboxRow(
                        id=event.event_id,
                        event_type=event.event_type,
                        payload=msgspec.json.encode(event),
                    )
                )
                await session.flush()
                await session.refresh(row, ["created_at"])
                created_at = row.created_at
        except IntegrityError as exc:
            raise EmailTakenError(email) from exc
        except SQLAlchemyError as exc:
            raise PortError(f"register user failed: {exc}") from exc
        return UserRecord(id=user_id, email=email, role=role, created_at=created_at)

    async def find_credentials_by_email(self, email: str) -> tuple[UserRecord, str] | None:
        try:
            async with self._sessionmaker() as session:
                result = await session.execute(
                    select(UserRow).where(UserRow.email == email, UserRow.deleted_at.is_(None))
                )
                row = result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise PortError(f"find user by email failed: {exc}") from exc
        return (to_user_record(row), row.password_hash) if row is not None else None

    async def is_active(self, user_id: UUID) -> bool:
        try:
            async with self._sessionmaker() as session:
                result = await session.execute(
                    select(UserRow.id).where(UserRow.id == user_id, UserRow.deleted_at.is_(None))
                )
                return result.scalar_one_or_none() is not None
        except SQLAlchemyError as exc:
            raise PortError(f"check user active failed: {exc}") from exc

    async def list_page(self, after: tuple[datetime, UUID] | None, limit: int) -> list[UserRecord]:
        stmt = (
            select(UserRow)
            .where(UserRow.deleted_at.is_(None))
            .order_by(UserRow.created_at.desc(), UserRow.id.desc())
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(keyset_older_than(UserRow.created_at, UserRow.id, after))
        try:
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
        except SQLAlchemyError as exc:
            raise PortError(f"list users page failed: {exc}") from exc
        return [to_user_record(r) for r in result.scalars().all()]

    async def soft_delete(self, user_id: UUID) -> bool:
        stmt = (
            update(UserRow)
            .where(UserRow.id == user_id, UserRow.deleted_at.is_(None))
            .values(deleted_at=func.now())
        )
        try:
            async with self._sessionmaker() as session, session.begin():
                cursor: CursorResult = await session.execute(stmt)
        except SQLAlchemyError as exc:
            raise PortError(f"soft delete user failed: {exc}") from exc
        return cursor.rowcount > 0
