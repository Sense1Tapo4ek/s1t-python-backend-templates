import os
from dataclasses import dataclass

import structlog

from ...config import MetricsConfig

_log = structlog.get_logger(__name__)


@dataclass(slots=True, kw_only=True)
class MetricsLifespanManager:
    config: MetricsConfig

    async def start(self) -> None:
        _log.info("metrics lifespan starting", multiproc_dir=str(self.config.multiproc_dir))
        # multiproc_dir is always a Path post-validation (resolved in MetricsConfig)
        assert self.config.multiproc_dir is not None, "multiproc_dir must be resolved by validator"
        os.makedirs(self.config.multiproc_dir, exist_ok=True)
        _log.info("metrics lifespan started")

    async def stop(self) -> None:
        _log.info("metrics lifespan stopping")
        try:
            from prometheus_client import multiprocess
            multiprocess.mark_process_dead(os.getpid())
        except Exception as e:
            _log.debug("mark_process_dead failed (no-op if multiproc inactive)", error=str(e))
        _log.info("metrics lifespan stopped")
