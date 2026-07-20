from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class OutboxMixin:
    """Columns for a per-context transactional outbox table.

    The owning context declares `class OutboxRow(OutboxMixin, Base)` on its own
    declarative Base, so the table lands in that context's schema and commits
    atomically with the context's aggregate rows through the same session.
    Drained out of band by `shared.adapters.driven.outbox_relay.OutboxRelay`.
    """

    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_type: Mapped[str]
    payload: Mapped[bytes]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
