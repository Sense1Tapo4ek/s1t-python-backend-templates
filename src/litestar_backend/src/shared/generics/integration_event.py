from datetime import datetime
from uuid import UUID

import msgspec


class IntegrationEvent(msgspec.Struct, frozen=True, kw_only=True):
    """Base envelope for outbound integration events.

    Subclasses add their payload fields and an `event_type` default; the
    envelope guarantees every event on the wire carries identity (`event_id`,
    consumer-side dedup key), a schema `version`, and `occurred_at` (producer
    clock, UTC). Consuming services define their OWN inbound schema by shape
    -- this class is never imported across the service boundary.
    """

    event_id: UUID
    occurred_at: datetime
    version: int = 1
