import json
from uuid import uuid4

import pytest
import pytest_asyncio

from media_processing.ports.driven import ValkeyEventPublisher
from shared.adapters.driven.valkey import build_valkey


@pytest_asyncio.fixture
async def valkey(valkey_url: str):
    client = build_valkey(valkey_url)
    await client.delete("video_status")
    try:
        yield client
    finally:
        await client.delete("video_status")
        await client.aclose()


class TestValkeyEventPublisher:
    @pytest.mark.asyncio
    async def test_publish_processed_appends_contract_entry(self, valkey) -> None:
        """
        Given a publisher over a live Valkey,
        When publish_processed is called,
        Then one video_status entry appears with the contract envelope and payload.
        """
        # Arrange
        publisher = ValkeyEventPublisher(_valkey=valkey)
        video_id = uuid4()

        # Act
        await publisher.publish_processed(video_id)

        # Assert
        entries = await valkey.xrange("video_status")
        assert len(entries) == 1
        _, fields = entries[0]
        assert fields["event_type"] == "video_processed"
        payload = json.loads(fields["payload"])
        assert payload["video_id"] == str(video_id)
        assert payload["event_type"] == "video_processed"
        assert payload["version"] == 1
        assert payload["event_id"] == fields["event_id"]
        assert "occurred_at" in payload

    @pytest.mark.asyncio
    async def test_each_event_type_lands_on_the_same_stream(self, valkey) -> None:
        """
        Given a publisher,
        When started, processed and failed are published for one video,
        Then three entries appear in FIFO order on video_status.
        """
        # Arrange
        publisher = ValkeyEventPublisher(_valkey=valkey)
        video_id = uuid4()

        # Act
        await publisher.publish_started(video_id)
        await publisher.publish_processed(video_id)
        await publisher.publish_failed(video_id)

        # Assert
        types = [f["event_type"] for _, f in await valkey.xrange("video_status")]
        assert types == ["video_processing_started", "video_processed", "video_processing_failed"]
