from uuid import UUID

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from auth.domain import ApiKeyRecord, UserRecord
from shared.adapters.driven.postgres import OutboxMixin, SoftDeleteMixin, TimestampMixin
from shared.domain.auth import Role


class Base(DeclarativeBase):
    pass


class ApiKeyRow(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    key_hash: Mapped[str]
    name: Mapped[str]
    role: Mapped[str]


class UserRow(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str]
    password_hash: Mapped[str]
    role: Mapped[str]


class OutboxRow(OutboxMixin, Base):
    __tablename__ = "outbox_messages"


def to_record(row: ApiKeyRow) -> ApiKeyRecord:
    return ApiKeyRecord(id=row.id, name=row.name, role=Role(row.role), created_at=row.created_at)


def to_user_record(row: UserRow) -> UserRecord:
    return UserRecord(id=row.id, email=row.email, role=Role(row.role), created_at=row.created_at)
