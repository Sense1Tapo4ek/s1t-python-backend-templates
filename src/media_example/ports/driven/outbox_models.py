from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class OutboxRow:
    id: UUID
    event_type: str
    payload: bytes
    created_at: datetime
