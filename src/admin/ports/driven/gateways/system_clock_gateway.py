from datetime import UTC, datetime

from ....app.interfaces import IClock


class SystemClockGateway(IClock):
    def now(self) -> datetime:
        return datetime.now(UTC)
