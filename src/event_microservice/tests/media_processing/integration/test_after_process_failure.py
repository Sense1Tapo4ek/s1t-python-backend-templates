from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from saq import Queue, Worker

from root.entrypoints.saq_worker import after_process, shutdown, startup
from shared.adapters.driven.valkey import build_valkey


@pytest_asyncio.fixture
async def valkey(valkey_url: str) -> aioredis.Redis:
    client = build_valkey(valkey_url)
    await client.delete("video_status")
    try:
        yield client
    finally:
        await client.delete("video_status")
        await client.aclose()


async def exploding(ctx: dict[str, Any], *, video_id: str) -> None:
    """A SAQ job function that always raises, triggering the failure path."""
    raise RuntimeError("boom")


class TestAfterProcessTerminalFailure:
    @pytest.mark.asyncio
    async def test_terminal_failure_publishes_failed_event_and_clears_join(
        self,
        valkey: aioredis.Redis,
        valkey_url: str,
        monkeypatch,
    ) -> None:
        """
        Given a SAQ job that always raises,
        When a burst worker drains it to terminal failure (attempts >= retries),
        Then video_processing_failed is published on video_status and the join key is cleared.
        """
        # Arrange
        monkeypatch.setenv("VALKEY_URL", valkey_url)
        video_id = uuid4()

        # Seed the join key so on_job_failed has something to clear.
        # The UC calls clear() unconditionally; a pre-existing key confirms the delete.
        await valkey.sadd(f"join:{video_id}", "stt")

        queue = Queue.from_url(valkey_url)
        await queue.connect()
        try:
            # retries defaults to 1 in SAQ; after one failure attempts=1 and
            # 1 < 1 is False, so after_process treats it as terminal.
            await queue.enqueue("exploding", video_id=str(video_id))

            worker = Worker(
                queue=queue,
                functions=[exploding],
                startup=startup,
                shutdown=shutdown,
                after_process=after_process,
                burst=True,
                dequeue_timeout=1.0,
            )

            # Act -- burst mode runs startup, fails the job, calls after_process, exits
            await worker.start()

            # Assert -- failed event published to video_status stream
            entries = await valkey.xrange("video_status")
            types = [f["event_type"] for _, f in entries]
            assert types == ["video_processing_failed"]

            # Assert -- join key was cleared by on_job_failed
            assert await valkey.exists(f"join:{video_id}") == 0
        finally:
            await queue.disconnect()
