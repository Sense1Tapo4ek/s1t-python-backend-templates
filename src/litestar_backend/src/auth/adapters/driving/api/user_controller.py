from typing import Annotated
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, Request, delete, get, post
from litestar.exceptions import NotAuthorizedException, ValidationException
from litestar.params import Parameter
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT

from shared.domain.auth import Principal, Role

from ....ports.driving import (
    AuthFacade,
    LoginRequest,
    MeResponse,
    Page,
    RegisterRequest,
    TokenPairResponse,
    UserResponse,
    decode_cursor,
)
from ....ports.driving.guards import require_role


class UserController(Controller):
    path = "/auth"
    tags = ["Auth"]  # noqa: RUF012

    @post("/register", status_code=HTTP_201_CREATED)
    @inject
    async def register(self, data: RegisterRequest, facade: FromDishka[AuthFacade]) -> UserResponse:
        return await facade.register(email=data.email, password=data.password)

    @post("/login", status_code=HTTP_200_OK)
    @inject
    async def login(self, data: LoginRequest, facade: FromDishka[AuthFacade]) -> TokenPairResponse:
        pair = await facade.login(email=data.email, password=data.password)
        if pair is None:
            raise NotAuthorizedException(detail="invalid credentials")
        return TokenPairResponse.of(pair)

    @get("/me", guards=[require_role(Role.USER, Role.ADMIN)], status_code=HTTP_200_OK)
    async def me(self, request: Request) -> MeResponse:
        principal: Principal = request.user
        return MeResponse(subject=principal.subject, role=principal.role.value)

    @get("/users", guards=[require_role(Role.ADMIN)], status_code=HTTP_200_OK)
    @inject
    async def list_users(
        self,
        facade: FromDishka[AuthFacade],
        cursor: Annotated[str | None, Parameter(required=False)] = None,
        limit: Annotated[int, Parameter(ge=1, le=200)] = 50,
    ) -> Page[UserResponse]:
        after = None
        if cursor is not None:
            try:
                after = decode_cursor(cursor)
            except ValueError as exc:
                raise ValidationException(detail="invalid cursor") from exc
        return await facade.list_users(after, limit)

    @delete(
        "/users/{user_id:uuid}",
        guards=[require_role(Role.ADMIN)],
        status_code=HTTP_204_NO_CONTENT,
    )
    @inject
    async def deactivate(self, user_id: UUID, facade: FromDishka[AuthFacade]) -> None:
        await facade.deactivate_user(user_id)
