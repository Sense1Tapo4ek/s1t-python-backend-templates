from dataclasses import dataclass

from ...domain import TokenPair, normalize_email
from ..errors import JwtDisabledError
from ..interfaces import IJwtService, IPasswordHasher, IUserRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class LoginUserUC:
    _users: IUserRepo
    _hasher: IPasswordHasher
    _jwt: IJwtService

    async def __call__(self, *, email: str, password: str) -> TokenPair | None:
        """None for ANY bad credential (unknown email, wrong password,
        deactivated account) -- the controller maps None to one uniform 401.

        Raises JwtDisabledError when no signing secret is configured (503).
        """
        found = await self._users.find_credentials_by_email(normalize_email(email))
        if found is None:
            # Same argon2 work as the real path: unknown email must not be
            # distinguishable from wrong password by response timing.
            self._hasher.verify(password, self._hasher.dummy_hash())
            return None
        user, password_hash = found
        if not self._hasher.verify(password, password_hash):
            return None
        pair = self._jwt.issue_pair(role=user.role, subject=str(user.id))
        if pair is None:
            raise JwtDisabledError()
        return pair
