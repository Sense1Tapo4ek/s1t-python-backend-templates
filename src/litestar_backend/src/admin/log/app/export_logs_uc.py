import csv
import io
from collections.abc import AsyncIterator
from dataclasses import dataclass

from ..domain import LogEntryVO, MalformedLogLine
from .interfaces import ILogReader

_CSV_HEADER = ("timestamp", "level", "logger", "event")

# Spreadsheet formula-injection mitigation: Excel/LibreOffice interpret cells
# starting with =+-@ as formulas; csv.writer quotes but does not defuse them.
_FORMULA_TRIGGERS = ("=", "+", "-", "@")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportLogsUC:
    """Streams the file as a download (NDJSON raw lines or parsed CSV).

    Backed by ILogReader.stream_all (a point-in-time snapshot of the file
    opened once). Memory is O(1) regardless of size. Malformed lines are
    skipped in CSV mode; NDJSON emits raw lines verbatim.
    """

    _reader: ILogReader

    async def export_ndjson(self) -> AsyncIterator[str]:
        async for line in self._reader.stream_all():
            yield line + "\n"

    async def export_csv(self) -> AsyncIterator[str]:
        buf = io.StringIO()
        writer = csv.writer(buf)

        writer.writerow(_CSV_HEADER)
        yield buf.getvalue()

        async for line in self._reader.stream_all():
            try:
                entry = LogEntryVO.parse(line)
            except MalformedLogLine:
                continue
            buf.seek(0)
            buf.truncate(0)
            writer.writerow(self._row(entry))
            yield buf.getvalue()

    @staticmethod
    def _row(entry: LogEntryVO) -> tuple[str, str, str, str]:
        return (
            _defuse(entry.timestamp),
            _defuse(entry.level),
            _defuse(entry.logger),
            _defuse(entry.event),
        )


def _defuse(value: str) -> str:
    if value and value[0] in _FORMULA_TRIGGERS:
        return "\t" + value
    return value
