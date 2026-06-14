from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared.adapters.driven.postgres import SoftDeleteMixin, TimestampMixin


class Base(DeclarativeBase):
    pass


class VideoRow(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "videos"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    source_key: Mapped[str]
    status: Mapped[str]
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    document: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class OutboxRow(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_type: Mapped[str]
    payload: Mapped[bytes]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
