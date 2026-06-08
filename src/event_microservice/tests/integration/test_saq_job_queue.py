from uuid import uuid4

import pytest
from saq import Queue

from media_processing.domain import JobKind
from media_processing.ports.driven import SaqJobQueue


class TestSaqJobQueue:
    @pytest.mark.asyncio
    async def test_enqueue_puts_a_job_on_the_queue(self, valkey_url: str) -> None:
        """Given a fresh queue, When enqueue is called, Then queue depth increases."""
        # Arrange
        queue = Queue.from_url(valkey_url)
        await queue.connect()
        try:
            before = await queue.count("queued")
            job_queue = SaqJobQueue(_queue=queue)

            # Act
            await job_queue.enqueue(uuid4(), JobKind.STT)

            # Assert
            assert await queue.count("queued") == before + 1
        finally:
            await queue.disconnect()
