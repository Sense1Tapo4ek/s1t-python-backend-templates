from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ...domain import UserRecord
from ..interfaces import IUserRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class ListUsersUC:
    _users: IUserRepo

    async def __call__(self, after: tuple[datetime, UUID] | None, limit: int) -> list[UserRecord]:
        return await self._users.list_page(after, limit)
