from collections.abc import AsyncGenerator
from typing import Protocol


class ILogBroadcaster(Protocol):
    """Fan-out channel. Each subscriber receives every record published
    after its subscription started. `subscribe()` returns an unbounded
    async generator."""

    def subscribe(self) -> AsyncGenerator[str, None]: ...

    async def broadcast(self, raw_json: str) -> None: ...

    async def broadcast_batch(self, items: list[str]) -> None: ...
