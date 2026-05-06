import asyncio

import structlog

from shared.logging import configure_structlog


def test_configure_structlog_uses_queue() -> None:
    queue = asyncio.Queue()
    configure_structlog(queue, app_name="test-app")

    logger = structlog.get_logger()
    logger.info("smoke")

    assert queue.qsize() == 1
    msg = queue.get_nowait()
    assert "smoke" in msg
