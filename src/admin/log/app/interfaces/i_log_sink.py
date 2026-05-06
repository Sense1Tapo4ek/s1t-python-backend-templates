from typing import Protocol


class ILogSink(Protocol):
    async def put(self, raw_json: str) -> None: ...
