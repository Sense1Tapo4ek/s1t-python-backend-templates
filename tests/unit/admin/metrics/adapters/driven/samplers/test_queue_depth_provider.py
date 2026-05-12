import asyncio

from admin.metrics.adapters.driven.samplers import RedisStreamQueueDepthProvider


class _FakePublisher:
    def __init__(self, items: int, dropped: int) -> None:
        self._buf: asyncio.Queue[str] = asyncio.Queue()
        for _ in range(items):
            self._buf.put_nowait("x")
        self._dropped = dropped

    @property
    def buffer(self):
        return self._buf


class TestRedisStreamQueueDepthProvider:
    def test_reads_qsize_and_dropped(self) -> None:
        pub = _FakePublisher(items=12, dropped=7)
        # _QueueLogger._dropped_total is a class-level counter. We
        # monkeypatch on the class for the test.
        from shared.logging import _QueueLogger
        _QueueLogger._dropped_total = 7

        provider = RedisStreamQueueDepthProvider(_publisher=pub)  # type: ignore[arg-type]
        assert provider.current_queue_depth() == 12
        assert provider.total_dropped() == 7

        _QueueLogger._dropped_total = 0
