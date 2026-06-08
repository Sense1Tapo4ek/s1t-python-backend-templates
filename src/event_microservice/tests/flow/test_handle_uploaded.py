from datetime import UTC, datetime
from uuid import uuid4

import msgspec
import pytest

from media_processing.adapters.driving import handle_uploaded


class _SpyFacade:
    def __init__(self) -> None:
        self.uploaded: list = []

    async def on_uploaded(self, video_id) -> None:
        self.uploaded.append(video_id)

    async def complete_job(self, video_id, kind) -> None: ...


def _payload(video_id) -> bytes:
    return msgspec.json.encode(
        {
            "event_id": str(uuid4()),
            "event_type": "video_uploaded",
            "version": 1,
            "video_id": str(video_id),
            "source_key": "uploads/clip.mp4",
            "uploaded_at": datetime.now(UTC).isoformat(),
        }
    )


class TestHandleUploaded:
    @pytest.mark.asyncio
    async def test_valid_payload_calls_facade(self) -> None:
        """Given a valid wire payload, When handled, Then the facade is called with the video_id."""
        facade = _SpyFacade()
        vid = uuid4()
        await handle_uploaded(_payload(vid), facade)
        assert facade.uploaded == [vid]

    @pytest.mark.asyncio
    async def test_malformed_payload_raises(self) -> None:
        """Given malformed JSON, When handled, Then msgspec raises (the subscriber catches+acks)."""
        facade = _SpyFacade()
        with pytest.raises(msgspec.MsgspecError):
            await handle_uploaded(b"{not json", facade)
        assert facade.uploaded == []
