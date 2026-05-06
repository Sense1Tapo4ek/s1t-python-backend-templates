import hashlib
import secrets
from dataclasses import dataclass

from shared.domain.auth import Principal, Role

from ....app.interfaces import ITokenResolver
from ....config import AuthConfig


def _token_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:8]


@dataclass(frozen=True, slots=True, kw_only=True)
class StaticTokenResolver(ITokenResolver):
    """Constant-time comparison defends against timing attacks."""

    _config: AuthConfig

    async def resolve(self, token: str) -> Principal | None:
        admin_token = self._config.admin_token
        if admin_token is None:
            return None
        admin_value = admin_token.get_secret_value()
        if not admin_value:
            return None
        if not secrets.compare_digest(token.encode(), admin_value.encode()):
            return None
        return Principal(role=Role.ADMIN, token_id=_token_id(token))
