from dataclasses import dataclass

from shared.domain.auth import Role

from ..domain import TokenPair
from .errors import JwtDisabledError
from .i_jwt_issuer import IJwtIssuer


@dataclass(frozen=True, slots=True, kw_only=True)
class IssueTokensUC:
    _issuer: IJwtIssuer

    def __call__(self, *, role: Role) -> TokenPair:
        pair = self._issuer.issue_pair(role=role)
        if pair is None:
            raise JwtDisabledError()
        return pair
