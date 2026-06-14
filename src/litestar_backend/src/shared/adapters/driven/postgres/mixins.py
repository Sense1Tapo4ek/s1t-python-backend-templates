from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """created_at / updated_at audit columns maintained by the database.

    created_at is set once on INSERT; updated_at is refreshed on ORM-emitted
    UPDATEs via onupdate. NOTE: a Core `INSERT ... ON CONFLICT DO UPDATE`
    (upsert) bypasses onupdate -- a repo using upsert must set updated_at
    explicitly in its conflict clause (see SqlVideoRepo.save).
    """

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    """deleted_at soft-delete marker. NULL means the row is active.

    Repositories MUST filter `deleted_at IS NULL` in every read so soft-deleted
    rows stay hidden while remaining on disk for audit/recovery.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
