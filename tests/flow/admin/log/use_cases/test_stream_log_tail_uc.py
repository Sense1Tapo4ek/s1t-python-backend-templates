import pytest

from admin.log.app.use_cases.stream_log_tail_uc import StreamLogTailUc
from admin.log.domain import LogEntryEnt


class _FakeFollower:
    def __init__(self, entries: list[LogEntryEnt], poll_seen: list[int]) -> None:
        self._entries = entries
        self._poll_seen = poll_seen

    async def follow(self, poll_ms: int):
        self._poll_seen.append(poll_ms)
        for e in self._entries:
            yield e


class TestStreamLogTailUc:
    @pytest.mark.asyncio
    async def test_yields_follower_entries_unfiltered(self) -> None:
        """
        Given a follower producing two entries,
        When the use case streams with a poll interval,
        Then both entries are yielded in order with no server-side filtering.
        """
        entries = [
            LogEntryEnt(timestamp="t1", level="INFO", logger="a", event="1", raw={}),
            LogEntryEnt(timestamp="t2", level="DEBUG", logger="b", event="2", raw={}),
        ]
        seen: list[int] = []
        uc = StreamLogTailUc(_follower=_FakeFollower(entries, seen))

        out = [e.event async for e in uc(poll_ms=250)]

        assert out == ["1", "2"]
        assert seen == [250]
