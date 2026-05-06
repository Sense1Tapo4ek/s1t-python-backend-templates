from collections.abc import AsyncGenerator
from dataclasses import dataclass, replace

import orjson

from shared.generics.json_utils import filter_raw_record

from ....app.use_cases import (
    ClearLogsUc,
    ExportLogsUc,
    LoadOlderLogsUc,
    RenderLogPageUc,
    StreamLogTailUc,
)
from ....domain import DslParser, LogEntryEnt, LogFilterVo, LogId
from ..schemas import LogEntrySchema, LogFilterSchema, LogPageResponseSchema

# Keys promoted to top-level columns in LogEntrySchema. Stripped from the
# JSON payload to avoid shipping every value twice over the SSE channel.
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


def _build_filter_vo(schema: LogFilterSchema | None) -> LogFilterVo | None:
    if schema is None:
        return None
    base = DslParser.parse(schema.q) if schema.q else LogFilterVo.empty()
    # Explicit schema fields override DSL where set. `levels` (multi-select)
    # takes precedence over `min_level`: if both are present, levels wins
    # and min_level is dropped to keep the SQL builder unambiguous.
    levels: tuple[str, ...] | None = (
        tuple(schema.levels) if schema.levels else base.levels
    )
    min_level = None if levels else (schema.min_level or base.min_level)
    return replace(
        base,
        min_level=min_level,
        levels=levels,
        live_mode=schema.live_mode or base.live_mode,
    )


def _to_entry_schema(ent: LogEntryEnt) -> LogEntrySchema:
    context = filter_raw_record(ent.raw_json, _PROMOTED_KEYS)
    # orjson emits compact JSON natively; bytes → str for the SSE payload.
    context_json = orjson.dumps(context).decode() if context else "{}"
    return LogEntrySchema(
        id=ent.id,
        timestamp=ent.timestamp,
        level=ent.level,
        logger=ent.logger,
        event=ent.event,
        pathname=ent.pathname,
        lineno=ent.lineno,
        func_name=ent.func_name,
        trace_id=ent.trace_id,
        span_id=ent.span_id,
        context_json=context_json,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class LogsFacade:
    """Public API of the admin log subsystem.

    Owns DSL parsing, pagination, SSE tail multiplexing, exports, and the
    admin clear action. `DslSyntaxError` and `InvalidLogFilterError` raised
    from `_to_filter_vo` propagate to the global handlers; callers must
    not catch them.
    """

    _render_log_page_uc: RenderLogPageUc
    _load_older_logs_uc: LoadOlderLogsUc
    _stream_log_tail_uc: StreamLogTailUc
    _export_logs_uc: ExportLogsUc
    _clear_logs_uc: ClearLogsUc

    async def render_log_page(
        self,
        schema: LogFilterSchema | None = None,
    ) -> LogPageResponseSchema:
        filter_vo = _build_filter_vo(schema)
        entries, cursor, has_more = await self._render_log_page_uc(filter_vo)
        return LogPageResponseSchema(
            entries=[_to_entry_schema(e) for e in entries],
            cursor=cursor,
            has_more=has_more,
        )

    async def load_older_logs(
        self,
        cursor_id: int,
        schema: LogFilterSchema | None = None,
    ) -> LogPageResponseSchema:
        filter_vo = _build_filter_vo(schema)
        entries, next_cursor, has_more = await self._load_older_logs_uc(
            LogId(cursor_id),
            filter_vo,
        )
        return LogPageResponseSchema(
            entries=[_to_entry_schema(e) for e in entries],
            cursor=next_cursor,
            has_more=has_more,
        )

    async def clear_logs(self) -> int:
        return await self._clear_logs_uc()

    def parse_filter(self, schema: LogFilterSchema | None) -> LogFilterVo | None:
        """Synchronous DSL validation hook for callers that need to surface
        DslSyntaxError before any streaming response starts."""
        return _build_filter_vo(schema)

    async def stream_tail(
        self,
        schema: LogFilterSchema | None = None,
    ) -> AsyncGenerator[LogEntrySchema, None]:
        filter_vo = _build_filter_vo(schema)
        async for entry in self._stream_log_tail_uc(filter_vo):
            yield _to_entry_schema(entry)

    async def export_ndjson(
        self,
        schema: LogFilterSchema | None = None,
    ) -> AsyncGenerator[str, None]:
        filter_vo = _build_filter_vo(schema)
        async for chunk in self._export_logs_uc.export_ndjson(filter_vo):
            yield chunk

    async def export_csv(
        self,
        schema: LogFilterSchema | None = None,
    ) -> AsyncGenerator[str, None]:
        filter_vo = _build_filter_vo(schema)
        async for chunk in self._export_logs_uc.export_csv(filter_vo):
            yield chunk
