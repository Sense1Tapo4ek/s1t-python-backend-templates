from collections.abc import AsyncGenerator
from dataclasses import dataclass

import orjson

from ...app import ExportLogsUC, ILogFollower, ILogReader
from ...domain import Cursor, LogEntryVO
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


def _to_entry_schema(ent: LogEntryVO) -> LogEntrySchema:
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
    """Driving port for the admin operator: the log-viewer surface.

    Public entry point of the `admin/log` context. Returns wire-ready
    LogEntrySchema rows and delegates reads to the query/use-case layer.
    """

    _reader: ILogReader
    _follower: ILogFollower
    _export_logs_uc: ExportLogsUC

    async def render_log_page(
        self,
        limit: int,
    ) -> tuple[list[LogEntrySchema], Cursor]:
        """Return the newest `limit` log rows, oldest-first, plus a back-cursor.

        The cursor points at the oldest returned row; pass it to
        load_older_logs to page further back. Propagates LogReadError if the
        log file cannot be read.
        """
        entries, cursor = await self._reader.read_tail(limit)
        return [_to_entry_schema(e) for e in entries], cursor

    async def load_older_logs(
        self,
        cursor: Cursor,
        limit: int,
    ) -> tuple[list[LogEntrySchema], Cursor]:
        """Return up to `limit` rows older than `cursor`, oldest-first.

        Returns the next back-cursor for continued paging. If the history
        behind the cursor was rotated away, returns no rows with the unchanged
        cursor (the caller stops paging). Propagates LogReadError if the log
        file cannot be read.
        """
        entries, next_cursor = await self._reader.read_before(cursor, limit)
        return [_to_entry_schema(e) for e in entries], next_cursor

    async def stream_tail(
        self,
        poll_ms: int,
    ) -> AsyncGenerator[LogEntrySchema, None]:
        """Yield newly-appended log rows as they arrive (live SSE tail).

        Starts at the current EOF (no history replay), polls every `poll_ms`
        ms, and never completes on its own -- the caller stops it by closing
        the generator on client disconnect.
        Survives rotation best-effort (at-most-once across the gap).
        """
        async for entry in self._follower.follow(poll_ms):
            yield _to_entry_schema(entry)

    async def export_ndjson(self) -> AsyncGenerator[str, None]:
        """Stream the whole file as NDJSON (raw JSONL lines, newline-terminated).

        Backed by a point-in-time snapshot opened once; O(1) memory. Lines
        are emitted verbatim.
        Propagates LogReadError if the file cannot be opened.
        """
        async for chunk in self._export_logs_uc.export_ndjson():
            yield chunk

    async def export_csv(self) -> AsyncGenerator[str, None]:
        """Stream the whole file as CSV (timestamp, level, logger, event).

        Emits a header row, then one row per parseable entry from a
        point-in-time snapshot (O(1) memory);
        malformed lines are skipped and cells are defused against spreadsheet
        formula injection. Propagates LogReadError if the file cannot be
        opened.
        """
        async for chunk in self._export_logs_uc.export_csv():
            yield chunk
