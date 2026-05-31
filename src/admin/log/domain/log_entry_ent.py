from dataclasses import dataclass
from typing import Any

import orjson

from .errors import MalformedLogLine


@dataclass(frozen=True, slots=True, kw_only=True)
class LogEntryEnt:
    timestamp: str
    level: str
    logger: str
    event: str
    raw: dict[str, Any]

    @classmethod
    def parse(cls, line: str) -> "LogEntryEnt":
        text = line.rstrip("\r")
        if not text:
            raise MalformedLogLine(preview=line)
        try:
            data = orjson.loads(text)
        except orjson.JSONDecodeError as exc:
            raise MalformedLogLine(preview=text[:200]) from exc
        if not isinstance(data, dict):
            raise MalformedLogLine(preview=text[:200])
        return cls(
            timestamp=str(data.get("timestamp", "")),
            level=str(data.get("level", "INFO")).upper(),
            logger=str(data.get("logger") or ""),
            event=str(data.get("event", "")),
            raw=data,
        )
