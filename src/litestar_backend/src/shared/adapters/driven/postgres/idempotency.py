from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class IdempotencyMixin:
    """Columns for a per-context idempotency-key table.

    The owning context declares `class IdempotencyRow(IdempotencyMixin, Base)`
    on its own declarative Base, so the table lands in that context's schema
    and the key claim commits atomically with the write it guards. `key` is the
    primary key: the uniqueness of the claim is the whole mechanism, and a
    concurrent duplicate blocks on this index until the first transaction
    resolves.

    `fingerprint` is the caller's hash of the request payload -- a replay with
    the same key but a different payload is a client bug, not a retry.
    `response` is the snapshot the owning context replays; `expires_at` is the
    retention horizon, enforced by whoever purges the table.
    """

    key: Mapped[str] = mapped_column(primary_key=True)
    fingerprint: Mapped[str]
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
