import pytest

from admin.log.app.use_cases.render_log_page_uc import RenderLogPageUc
from admin.log.domain import Cursor, LogEntryEnt


class _FakeReader:
    def __init__(self) -> None:
        self.called_with: int | None = None
        self._result = (
            [LogEntryEnt(timestamp="t", level="INFO", logger="a", event="x", raw={})],
            Cursor(inode=1, offset=5),
        )

    async def read_tail(self, limit: int):
        self.called_with = limit
        return self._result

    async def read_before(self, cursor, limit):  # pragma: no cover
        raise AssertionError("not used")

    def stream_all(self):  # pragma: no cover
        raise AssertionError("not used")


class TestRenderLogPageUc:
    @pytest.mark.asyncio
    async def test_delegates_to_read_tail(self) -> None:
        """
        Given a reader,
        When the use case is called with a limit,
        Then read_tail is invoked and its result returned verbatim.
        """
        reader = _FakeReader()
        uc = RenderLogPageUc(_reader=reader)

        entries, cursor = await uc(200)

        assert reader.called_with == 200
        assert entries[0].event == "x"
        assert cursor == Cursor(inode=1, offset=5)
