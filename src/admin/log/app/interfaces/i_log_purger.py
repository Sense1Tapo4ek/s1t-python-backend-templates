from typing import Protocol


class ILogPurger(Protocol):
    async def purge_all(self) -> int: ...
