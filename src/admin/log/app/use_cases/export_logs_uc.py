import csv
import io
from collections.abc import AsyncIterator
from dataclasses import dataclass

import orjson

from shared.generics.json_utils import filter_raw_record

from ...app.interfaces import ILogReader
from ...domain import LogFilterVo

_RESERVED_KEYS = frozenset({
    "timestamp", "level", "logger", "event",
    "pathname", "lineno", "func_name",
    "stack_info", "exception",
})

_CSV_HEADER = (
    "id", "timestamp", "level", "logger", "event",
    "pathname", "lineno", "func_name", "context",
)

# Spreadsheet formula-injection mitigation: Excel/LibreOffice interpret cells
# starting with =+-@ as formulas; csv.writer quotes but does not defuse them.
_FORMULA_TRIGGERS = ("=", "+", "-", "@")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportLogsUc:
    """Streams all matching entries to the caller without buffering.

    Memory is O(1) regardless of result size — backed by
    `ILogReader.stream_query`. CSV cells starting with formula triggers
    are defused with a leading tab (spreadsheet-injection mitigation).
    """

    _reader: ILogReader

    async def export_ndjson(
        self,
        filter_vo: LogFilterVo | None = None,
    ) -> AsyncIterator[str]:
        async for entry in self._reader.stream_query(filter_vo):
            yield entry.raw_json + "\n"

    async def export_csv(
        self,
        filter_vo: LogFilterVo | None = None,
    ) -> AsyncIterator[str]:
        # seek(0)+truncate(0) reuses the buffer; avoids per-row allocation
        # on large exports.
        buf = io.StringIO()
        writer = csv.writer(buf)

        writer.writerow(_CSV_HEADER)
        yield buf.getvalue()

        async for entry in self._reader.stream_query(filter_vo):
            context = _extract_context(entry.raw_json)
            buf.seek(0)
            buf.truncate(0)
            writer.writerow(
                (
                    entry.id,
                    entry.timestamp,
                    entry.level,
                    entry.logger,
                    _defuse(entry.event),
                    entry.pathname,
                    entry.lineno,
                    entry.func_name,
                    _defuse(context),
                ),
            )
            yield buf.getvalue()


def _defuse(value: str) -> str:
    if value and value[0] in _FORMULA_TRIGGERS:
        return "\t" + value
    return value


def _extract_context(raw_json: str) -> str:
    extras = filter_raw_record(raw_json, _RESERVED_KEYS)
    if not extras:
        return ""
    # orjson returns bytes; decode for the CSV column.
    return orjson.dumps(extras).decode()
