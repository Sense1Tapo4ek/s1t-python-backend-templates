from dataclasses import dataclass
from uuid import UUID

from ..errors import UserNotFound
from ..interfaces import IUserRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class DeactivateUserUC:
    _users: IUserRepo

    async def __call__(self, user_id: UUID) -> None:
        if not await self._users.soft_delete(user_id):
            raise UserNotFound(user_id)
