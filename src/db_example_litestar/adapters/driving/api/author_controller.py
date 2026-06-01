from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, delete, get, patch, post
from litestar.dto import DTOData
from litestar.pagination import OffsetPagination
from litestar.params import Parameter
from litestar.status_codes import HTTP_201_CREATED, HTTP_204_NO_CONTENT

# Hybrid context: driving adapters import the ORM model from adapters/driven so
# the SQLAlchemy DTOs can operate on it. CRUD itself goes through the facade
# (ports/driving), the context's single public API for both HTTP and code.
# Do NOT copy this model import into a strict context.
from ....adapters.driven.db.orm_models import AuthorModel
from ....ports.driving import AuthorFacade, AuthorPatchDTO, AuthorReadDTO, AuthorWriteDTO


class AuthorController(Controller):
    path = "/db-example-litestar/authors"
    return_dto = AuthorReadDTO

    @post("/", dto=AuthorWriteDTO, status_code=HTTP_201_CREATED)
    @inject
    async def create(
        self,
        data: DTOData[AuthorModel],
        facade: FromDishka[AuthorFacade],
    ) -> AuthorModel:
        return await facade.create(data.create_instance())

    @post("/bulk", dto=AuthorWriteDTO, status_code=HTTP_201_CREATED)
    @inject
    async def bulk_create(
        self,
        data: list[AuthorModel],
        facade: FromDishka[AuthorFacade],
    ) -> Sequence[AuthorModel]:
        # For a collection, let the DTO decode the JSON array straight into
        # model instances (DTOData.create_instance() is single-only).
        return await facade.create_many(data)

    @get("/")
    @inject
    async def list_authors(
        self,
        facade: FromDishka[AuthorFacade],
        search: Annotated[str, Parameter(max_length=200)] = "",
        limit: Annotated[int, Parameter(ge=1, le=200)] = 50,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[AuthorModel]:
        results, total = await facade.list(search=search, limit=limit, offset=offset)
        return OffsetPagination(items=list(results), total=total, limit=limit, offset=offset)

    @get("/{author_id:uuid}")
    @inject
    async def get_one(
        self,
        author_id: UUID,
        facade: FromDishka[AuthorFacade],
    ) -> AuthorModel:
        return await facade.get(author_id)

    @patch("/{author_id:uuid}", dto=AuthorPatchDTO)
    @inject
    async def update(
        self,
        author_id: UUID,
        data: DTOData[AuthorModel],
        facade: FromDishka[AuthorFacade],
    ) -> AuthorModel:
        return await facade.update(author_id, data.as_builtins())

    @delete("/{author_id:uuid}", status_code=HTTP_204_NO_CONTENT)
    @inject
    async def remove(
        self,
        author_id: UUID,
        facade: FromDishka[AuthorFacade],
    ) -> None:
        await facade.delete(author_id)
