from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .money_vo import Money


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderPlacedEvent:
    order_id: UUID
    total: Money
    placed_at: datetime
