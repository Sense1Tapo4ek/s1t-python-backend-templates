import pytest

from admin.log.app.log_queries import LogQueries
from admin.log.domain import Cursor, LogEntryEnt


class _FakeReader:
    def __init__(self, result=None) -> None:
        self.tail_limit: int | None = None
        self.before_args = None
        self._result = result or (
            [LogEntryEnt(timestamp="t", level="INFO", logger="a", event="x", raw={})],
            Cursor(inode=1, offset=5),
        )

    async def read_tail(self, limit: int):
        self.tail_limit = limit
        return self._result

    async def read_before(self, cursor, limit):
        self.before_args = (cursor, limit)
        return self._result

    def stream_all(self):  # pragma: no cover
        raise AssertionError("not used")


class _FakeFollower:
    def __init__(self, entries: list[LogEntryEnt], poll_seen: list[int]) -> None:
        self._entries = entries
        self._poll_seen = poll_seen

    async def follow(self, poll_ms: int):
        self._poll_seen.append(poll_ms)
        for e in self._entries:
            yield e


class TestRenderPage:
    @pytest.mark.asyncio
    async def test_delegates_to_read_tail(self) -> None:
        """
        Given a reader,
        When render_page is called with a limit,
        Then read_tail is invoked and its result returned verbatim.
        """
        # Arrange
        reader = _FakeReader()
        queries = LogQueries(_reader=reader, _follower=_FakeFollower([], []))

        # Act
        entries, cursor = await queries.render_page(200)

        # Assert
        assert reader.tail_limit == 200
        assert entries[0].event == "x"
        assert cursor == Cursor(inode=1, offset=5)


class TestLoadOlder:
    @pytest.mark.asyncio
    async def test_delegates_to_read_before(self) -> None:
        """
        Given a cursor and limit,
        When load_older is called,
        Then read_before is invoked and the page returned.
        """
        # Arrange
        cursor = Cursor(inode=2, offset=40)
        page = (
            [LogEntryEnt(timestamp="t", level="WARNING", logger="l", event="e", raw={})],
            Cursor(inode=2, offset=10),
        )
        reader = _FakeReader(page)
        queries = LogQueries(_reader=reader, _follower=_FakeFollower([], []))

        # Act
        entries, next_cursor = await queries.load_older(cursor, 100)

        # Assert
        assert reader.before_args == (cursor, 100)
        assert entries[0].event == "e"
        assert next_cursor == Cursor(inode=2, offset=10)

    @pytest.mark.asyncio
    async def test_rotation_sentinel_passes_through(self) -> None:
        """
        Given the reader returns the unchanged cursor with no entries,
        When load_older is called,
        Then the empty page and same cursor propagate (UI stops load-more).
        """
        # Arrange
        cursor = Cursor(inode=9, offset=99)
        reader = _FakeReader(([], cursor))
        queries = LogQueries(_reader=reader, _follower=_FakeFollower([], []))

        # Act
        entries, next_cursor = await queries.load_older(cursor, 50)

        # Assert
        assert entries == []
        assert next_cursor == cursor


class TestStreamTail:
    @pytest.mark.asyncio
    async def test_yields_follower_entries_unfiltered(self) -> None:
        """
        Given a follower producing two entries,
        When stream_tail is called with a poll interval,
        Then both entries are yielded in order with no server-side filtering.
        """
        # Arrange
        entries = [
            LogEntryEnt(timestamp="t1", level="INFO", logger="a", event="1", raw={}),
            LogEntryEnt(timestamp="t2", level="DEBUG", logger="b", event="2", raw={}),
        ]
        seen: list[int] = []
        queries = LogQueries(
            _reader=_FakeReader(), _follower=_FakeFollower(entries, seen)
        )

        # Act
        out = [e.event async for e in queries.stream_tail(poll_ms=250)]

        # Assert
        assert out == ["1", "2"]
        assert seen == [250]
