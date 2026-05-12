"""Lifespan manager for the admin/metrics subsystem.

Order of operations:
    start: loop-lag sampler  ->  publisher worker
    stop:  publisher worker  ->  loop-lag sampler
"""

import contextlib
from dataclasses import dataclass

import structlog

from ...app.interfaces import ILoopLagSampler
from ..driven.workers import MetricsPublisherWorker

_log = structlog.get_logger(__name__)


@dataclass(slots=True, kw_only=True)
class MetricsLifespanManager:
    _loop_lag_sampler: ILoopLagSampler
    _publisher_worker: MetricsPublisherWorker

    async def start(self) -> None:
        _log.info("metrics lifespan starting")
        await self._loop_lag_sampler.start()
        await self._publisher_worker.start()
        _log.info("metrics lifespan started")

    async def stop(self) -> None:
        _log.info("metrics lifespan stopping")
        with contextlib.suppress(Exception):
            await self._publisher_worker.stop()
        with contextlib.suppress(Exception):
            await self._loop_lag_sampler.stop()
        _log.info("metrics lifespan stopped")
