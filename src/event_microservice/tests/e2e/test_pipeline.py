from datetime import UTC, datetime
from uuid import uuid4

import msgspec
import pytest
import redis.asyncio as aioredis
from saq import Queue, Worker

from media_processing.adapters.driving import handle_uploaded, plagiarism, stt, transcode
from media_processing.ports.driving import MediaProcessingFacade
from root.composition.container import build_container
from root.entrypoints.saq_worker import shutdown, startup


def _wire_payload(video_id) -> bytes:
    """The JSON the producer puts in the stream entry's `payload` field."""
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


class TestPipeline:
    @pytest.mark.asyncio
    async def test_uploaded_event_drives_join_to_complete(self, valkey_url: str, monkeypatch) -> None:
        """
        Given a video_uploaded payload,
        When the consumer handler runs and the SAQ queue is burst-drained,
        Then 3 jobs run and the join reaches 3/3 and is cleared.
        """
        # Arrange
        monkeypatch.setenv("VALKEY_URL", valkey_url)
        monkeypatch.setenv("MEDIA_PROCESSING_FAKE_WORK_SECONDS", "0.0")
        monkeypatch.setenv("MEDIA_PROCESSING_TRANSCODE_ITERATIONS", "1000")
        # retries=0 keeps the assertion deterministic: with at-least-once retries a
        # redelivered job re-touches the join after it cleared (benign, TTL-bounded
        # in prod), which would leave the key present and fail the strict check.
        monkeypatch.setenv("MEDIA_PROCESSING_JOB_RETRIES", "0")
        video_id = uuid4()

        container = build_container()
        facade = await container.get(MediaProcessingFacade)
        queue = Queue.from_url(valkey_url)
        await queue.connect()
        try:
            # Act 1 -- the FastStream handler seam: parse + enqueue 3 jobs
            await handle_uploaded(_wire_payload(video_id), facade)
            assert await queue.count("queued") == 3

            # Act 2 -- burst-drain the worker
            worker = Worker(
                queue=queue,
                functions=[stt, plagiarism, transcode],
                startup=startup,
                shutdown=shutdown,
                burst=True,
                dequeue_timeout=1.0,
            )
            await worker.start()

            # Assert -- join completed and cleaned up; status events published
            client = aioredis.from_url(valkey_url, decode_responses=True)
            try:
                assert await client.exists(f"join:{video_id}") == 0
                assert await queue.count("queued") == 0
                status_entries = await client.xrange("video_status")
                types = [f["event_type"] for _, f in status_entries]
                assert "video_processing_started" in types
                assert "video_processed" in types
                await client.delete("video_status")
            finally:
                await client.aclose()
        finally:
            await queue.disconnect()
            await container.close()
