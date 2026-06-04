from typing import Protocol


class IEventBus(Protocol):
    async def publish(self, event: object) -> None: ...
