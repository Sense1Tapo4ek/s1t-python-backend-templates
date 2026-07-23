from collections.abc import AsyncIterator
from unittest.mock import create_autospec

import pytest

from admin.log.app import ExportLogsUC
from admin.log.domain import Cursor, LogEntryVO
from admin.log.ports.driving import LogsFacade


def _entry() -> LogEntryVO:
    return LogEntryVO.parse(
        '{"timestamp":"2026-06-01T00:00:00Z","level":"INFO","logger":"root","event":"hi","x":1}'
    )


class _FakeReader:
    async def read_tail(self, limit: int) -> tuple[list[LogEntryVO], Cursor]:
        return [_entry()], Cursor(inode=1, offset=0)

    async def read_before(self, cursor: Cursor, limit: int) -> tuple[list[LogEntryVO], Cursor]:
        return [_entry()], cursor

    def stream_all(self) -> AsyncIterator[str]:  # pragma: no cover
        raise AssertionError("not used")


class _FakeFollower:
    async def follow(self, poll_ms: int) -> AsyncIterator[LogEntryVO]:
        if False:  # pragma: no cover - empty async generator
            yield _entry()


@pytest.fixture
def facade() -> LogsFacade:
    export = create_autospec(ExportLogsUC, instance=True)
    return LogsFacade(
        _reader=_FakeReader(),
        _follower=_FakeFollower(),
        _export_logs_uc=export,
    )


class TestRenderLogPage:
    @pytest.mark.asyncio
    async def test_returns_entries_and_cursor(self, facade: LogsFacade) -> None:
        """
        Given a reader returning one entry and a cursor,
        When render_log_page is called,
        Then the response carries the entry schema and the Cursor.
        """
        # Act
        entries, cursor = await facade.render_log_page(limit=200)

        # Assert
        assert entries[0].event == "hi"
        assert cursor == Cursor(inode=1, offset=0)
        # promoted keys stripped from context_json, extra retained
        assert '"x":1' in entries[0].context_json.replace(" ", "")


class TestExport:
    @pytest.mark.asyncio
    async def test_export_ndjson_streams_raw_lines(self, facade: LogsFacade) -> None:
        """
        Given the export use case yields raw JSONL chunks,
        When export_ndjson is iterated,
        Then chunks pass through unchanged.
        """

        # Arrange
        async def _gen() -> AsyncIterator[str]:
            yield '{"event":"a"}\n'

        facade._export_logs_uc.export_ndjson = lambda: _gen()  # type: ignore[attr-defined]

        # Act
        out = [c async for c in facade.export_ndjson()]

        # Assert
        assert out == ['{"event":"a"}\n']
