import pytest

from admin.log.app.export_logs_uc import ExportLogsUc


class _FakeReader:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    async def read_tail(self, limit):  # pragma: no cover
        raise AssertionError("not used")

    async def read_before(self, cursor, limit):  # pragma: no cover
        raise AssertionError("not used")

    async def stream_all(self):
        for line in self._lines:
            yield line


class TestExportNdjson:
    @pytest.mark.asyncio
    async def test_streams_raw_lines_with_newline(self) -> None:
        """
        Given raw JSONL lines,
        When exporting NDJSON,
        Then each raw line is emitted verbatim with a trailing newline.
        """
        reader = _FakeReader([
            '{"event": "a", "level": "INFO"}',
            '{"event": "b", "level": "WARNING"}',
        ])
        uc = ExportLogsUc(_reader=reader)

        out = "".join([chunk async for chunk in uc.export_ndjson()])

        assert out == (
            '{"event": "a", "level": "INFO"}\n'
            '{"event": "b", "level": "WARNING"}\n'
        )


class TestExportCsv:
    @pytest.mark.asyncio
    async def test_emits_header_and_parsed_columns(self) -> None:
        """
        Given raw JSONL lines,
        When exporting CSV,
        Then a header row plus one row per parsed line is produced.
        """
        reader = _FakeReader([
            '{"timestamp": "t1", "level": "INFO", "logger": "a", "event": "started"}',
        ])
        uc = ExportLogsUc(_reader=reader)

        out = "".join([chunk async for chunk in uc.export_csv()])
        rows = out.strip().splitlines()

        assert rows[0] == "timestamp,level,logger,event"
        assert rows[1] == "t1,INFO,a,started"

    @pytest.mark.asyncio
    async def test_skips_malformed_lines(self) -> None:
        """
        Given a malformed line among valid ones,
        When exporting CSV,
        Then the malformed line is skipped (never raised).
        """
        reader = _FakeReader([
            "garbage",
            '{"timestamp": "t", "level": "INFO", "logger": "l", "event": "ok"}',
        ])
        uc = ExportLogsUc(_reader=reader)

        out = "".join([chunk async for chunk in uc.export_csv()])
        rows = out.strip().splitlines()

        assert len(rows) == 2  # header + one valid row
        assert rows[1].endswith("ok")

    @pytest.mark.asyncio
    async def test_defuses_formula_injection(self) -> None:
        """
        Given an event starting with a formula trigger,
        When exporting CSV,
        Then the cell is prefixed with a tab.
        """
        reader = _FakeReader([
            '{"timestamp": "t", "level": "INFO", "logger": "l", "event": "=SUM(A1)"}',
        ])
        uc = ExportLogsUc(_reader=reader)

        out = "".join([chunk async for chunk in uc.export_csv()])

        assert "\t=SUM(A1)" in out
