import asyncio
from unittest.mock import AsyncMock

import pytest

from admin.metrics.adapters.driven.workers import MetricsPublisherWorker

pytestmark = pytest.mark.asyncio


class TestMetricsPublisherWorker:
    async def test_ticks_call_use_case_until_stop(self) -> None:
        """
        Given a 50 ms publish interval,
        When the worker runs for ~150 ms then stops,
        Then the use case was invoked at least 2 times.
        """
        uc = AsyncMock()
        worker = MetricsPublisherWorker(_use_case=uc, _interval_s=0.05)

        await worker.start()
        await asyncio.sleep(0.16)
        await worker.stop()

        assert uc.await_count >= 2

    async def test_uc_exception_does_not_kill_loop(self) -> None:
        """
        Given a use case that raises once then succeeds,
        When the worker runs,
        Then later ticks still call the UC — observability never crashes.
        """
        calls = []

        async def flaky():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("first tick boom")

        worker = MetricsPublisherWorker(_use_case=flaky, _interval_s=0.02)
        await worker.start()
        await asyncio.sleep(0.1)
        await worker.stop()

        assert len(calls) >= 3
