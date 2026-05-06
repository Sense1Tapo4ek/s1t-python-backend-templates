"""Flow tests for ExportLogsUc — NDJSON streaming and CSV with context column."""

import csv
import io
import json
from collections.abc import AsyncIterator

import pytest

from admin.log.app.use_cases import ExportLogsUc
from admin.log.domain import LogEntryEnt, LogId


def _entry(
    *,
    id_: int,
    raw: dict,
    event: str = "x",
    level: str = "INFO",
    logger: str = "lg",
) -> LogEntryEnt:
    return LogEntryEnt(
        id=LogId(id_),
        timestamp="2026-05-06T00:00:00+00:00",
        level=level,
        logger=logger,
        event=event,
        pathname="/x.py",
        lineno=1,
        func_name="f",
        raw_json=json.dumps(raw),
    )


class _FakeReader:
    def __init__(self, entries: list[LogEntryEnt]) -> None:
        self._entries = entries

    async def stream_query(self, _filter) -> AsyncIterator[LogEntryEnt]:
        for e in self._entries:
            yield e

    # The other ILogReader methods are unused by ExportLogsUc.
    async def tail(self, *_a, **_k):  # pragma: no cover
        raise NotImplementedError

    async def read_before(self, *_a, **_k):  # pragma: no cover
        raise NotImplementedError


class TestExportNdjson:
    @pytest.mark.asyncio
    async def test_yields_one_line_per_entry(self) -> None:
        entries = [
            _entry(id_=1, raw={"event": "a", "user_id": "u1"}),
            _entry(id_=2, raw={"event": "b", "amount": 99}),
        ]
        uc = ExportLogsUc(_reader=_FakeReader(entries))

        chunks = [c async for c in uc.export_ndjson(None)]

        assert len(chunks) == 2
        for chunk in chunks:
            assert chunk.endswith("\n")
            json.loads(chunk)  # each chunk parses cleanly

    @pytest.mark.asyncio
    async def test_empty_reader_yields_nothing(self) -> None:
        uc = ExportLogsUc(_reader=_FakeReader([]))
        chunks = [c async for c in uc.export_ndjson(None)]
        assert chunks == []


class TestExportCsv:
    @pytest.mark.asyncio
    async def test_header_includes_context_column(self) -> None:
        uc = ExportLogsUc(_reader=_FakeReader([]))
        chunks = [c async for c in uc.export_csv(None)]
        assert len(chunks) == 1
        assert chunks[0].rstrip().endswith("context")

    @pytest.mark.asyncio
    async def test_context_column_carries_non_reserved_kwargs(self) -> None:
        """
        Given an entry with extra kwargs in raw_json,
        When export_csv streams,
        Then the `context` column contains a JSON dump of those kwargs only —
        reserved keys (timestamp/level/event/...) are excluded.
        """
        raw = {
            "timestamp": "x",
            "level": "INFO",
            "event": "ordered",
            "logger": "biz",
            "pathname": "p",
            "lineno": 1,
            "func_name": "f",
            "user_id": "u-42",
            "amount": 100,
        }
        uc = ExportLogsUc(_reader=_FakeReader([_entry(id_=7, raw=raw)]))
        chunks = [c async for c in uc.export_csv(None)]

        # First chunk = header, second = the row.
        rows = list(csv.reader(io.StringIO("".join(chunks))))
        assert rows[0][-1] == "context"
        context = json.loads(rows[1][-1])
        assert context == {"user_id": "u-42", "amount": 100}

    @pytest.mark.asyncio
    async def test_context_empty_when_no_extras(self) -> None:
        raw = {"timestamp": "x", "level": "INFO", "event": "e", "logger": "l",
               "pathname": "p", "lineno": 1, "func_name": "f"}
        uc = ExportLogsUc(_reader=_FakeReader([_entry(id_=1, raw=raw)]))
        chunks = [c async for c in uc.export_csv(None)]
        rows = list(csv.reader(io.StringIO("".join(chunks))))
        assert rows[1][-1] == ""

    @pytest.mark.asyncio
    async def test_context_resilient_to_invalid_raw_json(self) -> None:
        ent = LogEntryEnt(
            id=LogId(1),
            timestamp="t", level="INFO", logger="l", event="e",
            pathname="p", lineno=1, func_name="f",
            raw_json="not-json-at-all",
        )
        uc = ExportLogsUc(_reader=_FakeReader([ent]))
        chunks = [c async for c in uc.export_csv(None)]
        rows = list(csv.reader(io.StringIO("".join(chunks))))
        assert rows[1][-1] == ""

    @pytest.mark.parametrize("trigger", ["=", "+", "-", "@"])
    @pytest.mark.asyncio
    async def test_event_starting_with_formula_trigger_gets_tab_prefix(
        self,
        trigger: str,
    ) -> None:
        """
        Given a log event starting with =/+/-/@,
        When export_csv streams the row,
        Then the value is prefixed with a tab — Excel/LibreOffice show it as
        text instead of evaluating as a formula.
        """
        ent = _entry(id_=1, raw={"event": f"{trigger}HYPERLINK(\"x\")"},
                     event=f"{trigger}HYPERLINK(\"x\")")
        uc = ExportLogsUc(_reader=_FakeReader([ent]))
        chunks = [c async for c in uc.export_csv(None)]
        rows = list(csv.reader(io.StringIO("".join(chunks))))
        # Event column (index 4) starts with a tab.
        assert rows[1][4].startswith("\t"), rows[1]
