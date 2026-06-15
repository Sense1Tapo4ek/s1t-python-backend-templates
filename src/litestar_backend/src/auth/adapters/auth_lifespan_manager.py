from dataclasses import dataclass

from shared.adapters.driven.postgres import run_migrations
from shared.generics.config import PROJECT_ROOT

_MIGRATIONS_DIR = str(PROJECT_ROOT / "migrations" / "auth")


@dataclass(slots=True, kw_only=True)
class AuthLifespanManager:
    yoyo_url: str

    async def start(self) -> None:
        await run_migrations(self.yoyo_url, _MIGRATIONS_DIR)

    async def stop(self) -> None:
        return None
