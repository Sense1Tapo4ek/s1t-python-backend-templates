from collections.abc import AsyncGenerator
from dataclasses import dataclass

import orjson

from ...app import (
    ExportLogsUc,
    LoadOlderLogsUc,
    RenderLogPageUc,
    StreamLogTailUc,
)
from ...domain import Cursor, LogEntryEnt
from .log_schemas import LogEntrySchema

# Promoted to top-level columns in LogEntrySchema; stripped from context_json
# so each value ships once.
_PROMOTED_KEYS = frozenset(
    {
        "timestamp",
        "level",
        "logger",
        "event",
        "pathname",
        "lineno",
        "func_name",
        "trace_id",
        "span_id",
    }
)


def _to_entry_schema(ent: LogEntryEnt) -> LogEntrySchema:
    context = {k: v for k, v in ent.raw.items() if k not in _PROMOTED_KEYS}
    context_json = orjson.dumps(context).decode() if context else "{}"
    return LogEntrySchema(
        timestamp=ent.timestamp,
        level=ent.level,
        logger=ent.logger,
        event=ent.event,
        pathname=ent.raw.get("pathname"),
        lineno=ent.raw.get("lineno"),
        func_name=ent.raw.get("func_name"),
        trace_id=ent.raw.get("trace_id"),
        span_id=ent.raw.get("span_id"),
        context_json=context_json,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class LogsFacade:
    _render_log_page_uc: RenderLogPageUc
    _load_older_logs_uc: LoadOlderLogsUc
    _stream_log_tail_uc: StreamLogTailUc
    _export_logs_uc: ExportLogsUc

    async def render_log_page(
        self,
        limit: int,
    ) -> tuple[list[LogEntrySchema], Cursor | None]:
        entries, cursor = await self._render_log_page_uc.__call__(limit)
        return [_to_entry_schema(e) for e in entries], cursor

    async def load_older_logs(
        self,
        cursor: Cursor,
        limit: int,
    ) -> tuple[list[LogEntrySchema], Cursor | None]:
        entries, next_cursor = await self._load_older_logs_uc.__call__(cursor, limit)
        return [_to_entry_schema(e) for e in entries], next_cursor

    async def stream_tail(
        self,
        poll_ms: int,
    ) -> AsyncGenerator[LogEntrySchema, None]:
        async for entry in self._stream_log_tail_uc.__call__(poll_ms):
            yield _to_entry_schema(entry)

    async def export_ndjson(self) -> AsyncGenerator[str, None]:
        async for chunk in self._export_logs_uc.export_ndjson():
            yield chunk

    async def export_csv(self) -> AsyncGenerator[str, None]:
        async for chunk in self._export_logs_uc.export_csv():
            yield chunk
