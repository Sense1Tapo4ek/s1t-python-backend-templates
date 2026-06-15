from uuid import UUID

from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, delete, get, post
from litestar.status_codes import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from shared.domain.auth import Role

from ....ports.driving import (
    ApiKeyResponse,
    AuthFacade,
    CreateApiKeyRequest,
    CreatedApiKeyResponse,
)
from ....ports.driving.guards import require_role


class ApiKeyController(Controller):
    path = "/auth/api-keys"
    tags = ["Auth"]  # noqa: RUF012
    guards = [require_role(Role.ADMIN)]  # noqa: RUF012

    @post(status_code=HTTP_201_CREATED)
    @inject
    async def create(
        self, data: CreateApiKeyRequest, facade: FromDishka[AuthFacade]
    ) -> CreatedApiKeyResponse:
        """Mint a new ADMIN API key. The plaintext key is returned ONCE."""
        api_key_id, plaintext = await facade.generate_api_key(name=data.name)
        return CreatedApiKeyResponse(
            id=api_key_id, name=data.name, api_key=plaintext, role=Role.ADMIN.value
        )

    @get()
    @inject
    async def list_keys(self, facade: FromDishka[AuthFacade]) -> list[ApiKeyResponse]:
        """List active API keys (never returns the secret)."""
        return [ApiKeyResponse.of(r) for r in await facade.list_api_keys()]

    @delete("/{api_key_id:uuid}", status_code=HTTP_204_NO_CONTENT)
    @inject
    async def revoke(self, api_key_id: UUID, facade: FromDishka[AuthFacade]) -> None:
        """Revoke (soft-delete) an API key. 404 if no active key with that id."""
        await facade.revoke_api_key(api_key_id)
