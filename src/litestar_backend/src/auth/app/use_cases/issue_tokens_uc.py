from dataclasses import dataclass

from shared.domain.auth import Role

from ...domain import TokenPair
from ..errors import JwtDisabledError
from ..interfaces import IJwtService


@dataclass(frozen=True, slots=True, kw_only=True)
class IssueTokensUC:
    _jwt: IJwtService

    def __call__(self, *, role: Role) -> TokenPair:
        pair = self._jwt.issue_pair(role=role)
        if pair is None:
            raise JwtDisabledError()
        return pair
