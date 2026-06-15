from typing import Protocol

from shared.domain.auth import Role

from ..domain import TokenPair


class IJwtIssuer(Protocol):
    def issue_pair(self, *, role: Role) -> TokenPair | None:
        """Mint a fresh access+refresh pair for `role`.

        Each token carries a unique `jti`. Returns None iff JWT is disabled
        (no signing secret configured) -- callers map that to a 503.
        """
        ...
