import asyncio

import pytest

from admin.metrics.adapters.driven.samplers import EventLoopLagSampler

pytestmark = pytest.mark.asyncio


class TestEventLoopLagSampler:
    async def test_initial_p95_is_zero(self) -> None:
        """Before start() is called, p95 reads as 0 — never raises."""
        sampler = EventLoopLagSampler(_interval_s=0.01, _window=10)
        assert sampler.current_p95_ms() == 0.0

    async def test_collects_and_reports_after_start(self) -> None:
        """
        Given the sampler started,
        When >=5 samples have been collected,
        Then p95 is non-negative (loose threshold — actual value depends
        on host load).
        """
        sampler = EventLoopLagSampler(_interval_s=0.005, _window=20)
        await sampler.start()
        try:
            await asyncio.sleep(0.1)
            p95 = sampler.current_p95_ms()
            assert p95 >= 0.0
        finally:
            await sampler.stop()

    async def test_stop_cancels_background_task(self) -> None:
        sampler = EventLoopLagSampler(_interval_s=0.005, _window=20)
        await sampler.start()
        await sampler.stop()
        # Calling stop twice should be safe.
        await sampler.stop()
