import pytest

from admin.log.app.use_cases.load_older_logs_uc import LoadOlderLogsUc
from admin.log.domain import Cursor, LogEntryEnt


class _FakeReader:
    def __init__(self, result) -> None:
        self.args = None
        self._result = result

    async def read_tail(self, limit):  # pragma: no cover
        raise AssertionError("not used")

    async def read_before(self, cursor, limit):
        self.args = (cursor, limit)
        return self._result

    def stream_all(self):  # pragma: no cover
        raise AssertionError("not used")


class TestLoadOlderLogsUc:
    @pytest.mark.asyncio
    async def test_delegates_to_read_before(self) -> None:
        """
        Given a cursor and limit,
        When the use case is called,
        Then read_before is invoked and the page returned.
        """
        cursor = Cursor(inode=2, offset=40)
        page = (
            [LogEntryEnt(timestamp="t", level="WARNING", logger="l", event="e", raw={})],
            Cursor(inode=2, offset=10),
        )
        reader = _FakeReader(page)
        uc = LoadOlderLogsUc(_reader=reader)

        entries, next_cursor = await uc(cursor, 100)

        assert reader.args == (cursor, 100)
        assert entries[0].event == "e"
        assert next_cursor == Cursor(inode=2, offset=10)

    @pytest.mark.asyncio
    async def test_rotation_sentinel_passes_through(self) -> None:
        """
        Given the reader returns the unchanged cursor with no entries,
        When the use case is called,
        Then the empty page and same cursor propagate (UI stops load-more).
        """
        cursor = Cursor(inode=9, offset=99)
        reader = _FakeReader(([], cursor))
        uc = LoadOlderLogsUc(_reader=reader)

        entries, next_cursor = await uc(cursor, 50)

        assert entries == []
        assert next_cursor == cursor
