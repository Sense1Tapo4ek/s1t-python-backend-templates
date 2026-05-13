from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar

E = TypeVar("E")


class IEventBus(Protocol):
    """Async pub/sub for typed domain events.

    Lifecycle: subscribe() at wire-up, start() once at lifespan, publish()
    after each commit, stop() at shutdown. Handler exceptions are caught
    and logged — one bad handler never stops the worker or its siblings.
    """

    async def publish(self, event: object) -> None:
        """Enqueue `event` for every handler of `type(event)`; returns immediately."""

    def subscribe(
        self,
        event_type: type[E],
        handler: Callable[[E], Awaitable[None]],
    ) -> None:
        """Register handler for `event_type`. Must be called before start()."""

    async def start(self) -> None:
        """Spin up per-handler worker tasks. Idempotent."""

    async def stop(self) -> None:
        """Cancel and await all worker tasks. Idempotent."""
