from dataclasses import dataclass
from typing import Protocol

from ...app import IEventBus
from ...domain import OrderPlacedEvent


class _Emitter(Protocol):
    # Local protocol for the Litestar app's emit(); injected via DI so this
    # driven port stays framework-free (no litestar import here).
    def emit(self, event_id: str, /, **kwargs: object) -> None: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class LitestarEventBus(IEventBus):
    _emitter: _Emitter

    async def publish(self, event: object) -> None:
        match event:
            case OrderPlacedEvent(order_id=oid, total=total, placed_at=ts):
                self._emitter.emit(
                    "order_placed",
                    order_id=str(oid),
                    amount=str(total.amount),
                    currency=total.currency,
                    placed_at=ts.isoformat(),
                )
            case _:
                # Unknown event types are ignored: this bus only maps what it knows.
                pass
