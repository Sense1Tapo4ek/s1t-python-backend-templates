from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, create_autospec

import pytest

from admin.log.app import ExportLogsUc, LogQueries
from admin.log.domain import Cursor, LogEntryEnt
from admin.log.ports.driving import LogsFacade


def _entry() -> LogEntryEnt:
    return LogEntryEnt.parse(
        '{"timestamp":"2026-06-01T00:00:00Z","level":"INFO",'
        '"logger":"root","event":"hi","x":1}'
    )


@pytest.fixture
def facade() -> LogsFacade:
    queries = create_autospec(LogQueries, instance=True)
    queries.render_page = AsyncMock(
        return_value=([_entry()], Cursor(inode=1, offset=0))
    )
    queries.load_older = AsyncMock(return_value=([_entry()], None))
    export = create_autospec(ExportLogsUc, instance=True)
    return LogsFacade(
        _log_queries=queries,
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
