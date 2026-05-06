from dataclasses import dataclass

import structlog

from ...app.interfaces import ILogPurger

_log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class ClearLogsUc:
    _purger: ILogPurger

    async def __call__(self) -> int:
        deleted = await self._purger.purge_all()
        _log.warning("logs purged", deleted=deleted)
        return deleted
