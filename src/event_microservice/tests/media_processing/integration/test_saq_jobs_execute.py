from uuid import uuid4

import pytest
from saq import Queue, Worker

from media_processing.adapters.driving import plagiarism, stt, transcode
from media_processing.domain import JobKind
from root.entrypoints.saq_worker import shutdown, startup


class TestSaqJobsExecute:
    @pytest.mark.asyncio
    async def test_three_jobs_complete_the_join(self, valkey_url: str, monkeypatch) -> None:
        """
        Given the 3 jobs enqueued for one video,
        When a burst worker drains the queue,
        Then each job runs its model and the join completes (key cleared).
        """
        # Arrange -- point both the worker container and SAQ at the test Valkey
        monkeypatch.setenv("VALKEY_URL", valkey_url)
        monkeypatch.setenv("MEDIA_PROCESSING_FAKE_WORK_SECONDS", "0.0")
        monkeypatch.setenv("MEDIA_PROCESSING_TRANSCODE_ITERATIONS", "1000")
        vid = uuid4()
        queue = Queue.from_url(valkey_url)
        await queue.connect()
        try:
            for kind in JobKind:
                await queue.enqueue(kind.value, video_id=str(vid))

            worker = Worker(
                queue=queue,
                functions=[stt, plagiarism, transcode],
                startup=startup,
                shutdown=shutdown,
                burst=True,
                dequeue_timeout=1.0,
            )

            # Act -- burst mode runs startup, drains all queued jobs, runs shutdown, exits
            await worker.start()

            # Assert -- the 3rd completion cleared the join key
            import redis.asyncio as aioredis

            client = aioredis.from_url(valkey_url, decode_responses=True)
            try:
                assert await client.exists(f"join:{vid}") == 0
                assert await queue.count("queued") == 0
            finally:
                await client.aclose()
        finally:
            await queue.disconnect()
