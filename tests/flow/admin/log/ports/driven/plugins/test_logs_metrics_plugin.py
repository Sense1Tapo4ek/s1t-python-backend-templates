from unittest.mock import MagicMock

import pytest
import pytest_asyncio
import fakeredis.aioredis

from admin.log.ports.driven.plugins import LogsMetricsPlugin
from tests.conftest_helpers.plugin_contract import assert_plugin_contract

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=False)
    try:
        yield r
    finally:
        await r.aclose()


class TestLogsMetricsPlugin:
    async def test_summary_reads_stream_length_and_pel(self, redis) -> None:
        """
        Given a stream with 5 entries and 2 pending in a consumer group,
        When calling summary(),
        Then the result contains stream length and pending KVs.
        """
        for i in range(5):
            await redis.xadd("logs", {"raw": "x"})
        await redis.xgroup_create("logs", "logsink", id="0", mkstream=True)
        await redis.xreadgroup("logsink", "c1", {"logs": ">"}, count=2)

        publisher = MagicMock()
        publisher.buffer = MagicMock()
        publisher.buffer.qsize.return_value = 12

        plugin = LogsMetricsPlugin(
            _redis=redis,
            _publisher=publisher,
            _stream_key="logs",
            _consumer_group="logsink",
            _stream_maxlen=100_000,
            _batch_size=100,
        )
        s = await plugin.summary()
        labels = {kv.label: kv.value for kv in s.kvs}
        assert any("stream" in k for k in labels)
        assert any("pending" in k for k in labels)

    async def test_contract(self, redis) -> None:
        """
        Given a LogsMetricsPlugin instance,
        When asserting the plugin contract,
        Then all contract assertions pass.
        """
        publisher = MagicMock()
        publisher.buffer = MagicMock()
        publisher.buffer.qsize.return_value = 0

        plugin = LogsMetricsPlugin(
            _redis=redis,
            _publisher=publisher,
            _stream_key="logs",
            _consumer_group="logsink",
            _stream_maxlen=100_000,
            _batch_size=100,
        )
        await assert_plugin_contract(plugin)
