from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, post
from litestar.exceptions import NotAuthorizedException
from litestar.status_codes import HTTP_200_OK, HTTP_204_NO_CONTENT

from shared.domain.auth import Role

from ....ports.driving import (
    AuthFacade,
    RefreshRequest,
    RevokeRequest,
    TokenPairResponse,
)
from ....ports.driving.guards import require_role


class TokenController(Controller):
    path = "/auth"
    tags = ["Auth"]  # noqa: RUF012

    @post("/token", guards=[require_role(Role.ADMIN)], status_code=HTTP_200_OK)
    @inject
    async def issue(self, facade: FromDishka[AuthFacade]) -> TokenPairResponse:
        """Mint an access+refresh pair. Bootstrap auth: ADMIN credential required."""
        return TokenPairResponse.of(facade.issue_tokens(role=Role.ADMIN))

    @post("/refresh", status_code=HTTP_200_OK)
    @inject
    async def refresh(
        self, data: RefreshRequest, facade: FromDishka[AuthFacade]
    ) -> TokenPairResponse:
        """Rotate a refresh token into a new pair; the old refresh is revoked."""
        pair = await facade.refresh_tokens(data.refresh_token)
        if pair is None:
            raise NotAuthorizedException(detail="invalid or expired refresh token")
        return TokenPairResponse.of(pair)

    @post("/revoke", status_code=HTTP_204_NO_CONTENT)
    @inject
    async def revoke(self, data: RevokeRequest, facade: FromDishka[AuthFacade]) -> None:
        """Revoke a token (logout). Idempotent: invalid input is a 204 no-op."""
        await facade.revoke_token(data.token)
