import pytest

from admin.log.app.use_cases import LoadOlderLogsUc, RenderLogPageUc, StreamLogTailUc
from admin.log.domain import LogEntryEnt, LogFilterVo, LogId


class _FakeLogReader:
    def __init__(self, entries: list[LogEntryEnt]) -> None:
        self._entries = entries

    async def tail(
        self,
        size: int,
        filter_vo: LogFilterVo | None = None,
    ) -> tuple[list[LogEntryEnt], LogId | None, bool]:
        result = self._entries[-size:]
        cursor = result[0].id if result else None
        has_more = len(self._entries) > size
        return result, cursor, has_more

    async def read_before(
        self,
        cursor: LogId,
        size: int,
        filter_vo: LogFilterVo | None = None,
    ) -> tuple[list[LogEntryEnt], LogId | None, bool]:
        before = [e for e in self._entries if e.id < cursor]
        result = before[-size:]
        next_cursor = result[0].id if result else None
        has_more = len(before) > size
        return result, next_cursor, has_more

    async def stream_after(
        self,
        cursor: LogId | None = None,
        filter_vo: LogFilterVo | None = None,
    ):
        start_id = cursor if cursor is not None else -1
        for entry in self._entries:
            if entry.id > start_id:
                yield entry

    async def stream_query(
        self,
        filter_vo: LogFilterVo | None = None,
    ):
        for entry in self._entries:
            yield entry


def _entry(id_: int, level: str = "INFO", event: str = "msg") -> LogEntryEnt:
    return LogEntryEnt(
        id=LogId(id_),
        timestamp="2026-04-29T12:00:00+00:00",
        level=level,
        logger="test",
        event=event,
        pathname="test.py",
        lineno=1,
        func_name="test",
        raw_json=f'{{"event": "{event}"}}',
    )


@pytest.mark.anyio
async def test_render_log_page_returns_tail() -> None:
    entries = [_entry(i, event=f"m-{i}") for i in range(5)]
    reader = _FakeLogReader(entries)
    uc = RenderLogPageUc(_reader=reader, _tail_size=3)

    result, cursor, has_more = await uc()

    assert [e.event for e in result] == ["m-2", "m-3", "m-4"]
    assert cursor == 2
    assert has_more is True


@pytest.mark.anyio
async def test_load_older_logs_returns_chunk() -> None:
    entries = [_entry(i, event=f"m-{i}") for i in range(5)]
    reader = _FakeLogReader(entries)
    render_uc = RenderLogPageUc(_reader=reader, _tail_size=2)
    _, cursor, _ = await render_uc()
    assert cursor is not None

    load_uc = LoadOlderLogsUc(_reader=reader, _chunk_size=2)
    result, next_cursor, has_more = await load_uc(cursor)

    assert [e.event for e in result] == ["m-1", "m-2"]
    assert next_cursor == 1
    # m-0 is older than the returned chunk → has_more reflects that.
    assert has_more is True


@pytest.mark.anyio
async def test_stream_log_tail_yields_entries() -> None:
    entries = [_entry(i, event=f"m-{i}") for i in range(3)]
    reader = _FakeLogReader(entries)
    uc = StreamLogTailUc(_reader=reader)

    result = [e async for e in uc()]

    assert [e.event for e in result] == ["m-0", "m-1", "m-2"]
