from dataclasses import dataclass

from shared.domain.auth import Role

from ...domain import UserRecord, normalize_email
from ..interfaces import IPasswordHasher, IUserRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class RegisterUserUC:
    _users: IUserRepo
    _hasher: IPasswordHasher

    async def __call__(self, *, email: str, password: str) -> UserRecord:
        return await self._users.register(
            email=normalize_email(email),
            password_hash=self._hasher.hash(password),
            role=Role.USER,
        )
