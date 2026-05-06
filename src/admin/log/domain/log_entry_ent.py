from dataclasses import dataclass

from .types import LogId


@dataclass(frozen=True, slots=True, kw_only=True)
class LogEntryEnt:
    id: LogId
    timestamp: str
    level: str
    logger: str
    event: str
    pathname: str
    lineno: int
    func_name: str
    raw_json: str
    trace_id: str | None = None
    span_id: str | None = None
