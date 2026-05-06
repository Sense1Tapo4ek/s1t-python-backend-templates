from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar

E = TypeVar("E")


class IEventBus(Protocol):
    """Async pub/sub for typed domain events.

    Wire-format and transport are abstracted away. The default implementation
    routes through Litestar's ChannelsPlugin (in-process MemoryChannelsBackend),
    but the same Protocol can be implemented over Redis, Kafka, etc.

    Lifecycle:
      1. At wire-up time, callers register handlers via `subscribe(EventType, handler)`.
      2. The application calls `start()` once during lifespan startup; the bus
         spins up one background task per (event_type, handler) pair.
      3. Use cases call `publish(event)` after their transactional work commits.
      4. The application calls `stop()` during lifespan shutdown; all worker
         tasks are cancelled and awaited.

    Failure semantics: handler exceptions are caught and logged; one bad
    handler never stops the worker or affects sibling handlers.
    """

    async def publish(self, event: object) -> None:
        """Send `event` to every handler registered for `type(event)`.

        Returns immediately after enqueuing — handlers run asynchronously.
        """

    def subscribe(
        self,
        event_type: type[E],
        handler: Callable[[E], Awaitable[None]],
    ) -> None:
        """Register `handler` to be called for every published event of type
        `event_type`. Must be called before `start()`.
        """

    async def start(self) -> None:
        """Spin up the per-handler worker tasks. Idempotent."""

    async def stop(self) -> None:
        """Cancel and await all worker tasks. Idempotent."""
