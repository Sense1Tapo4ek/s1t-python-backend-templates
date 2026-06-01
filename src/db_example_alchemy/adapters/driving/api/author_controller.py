from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from advanced_alchemy.filters import LimitOffset, OrderBy, SearchFilter
from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, delete, get, patch, post
from litestar.dto import DTOData
from litestar.pagination import OffsetPagination
from litestar.params import Parameter
from litestar.status_codes import HTTP_201_CREATED, HTTP_204_NO_CONTENT

# Hybrid context: driving adapters import the ORM model from adapters/driven.
# This relaxes the strict S-DDD layer rule on purpose (advanced-alchemy DTOs
# operate on the ORM model). Do NOT copy this import pattern into a strict
# context.
from ....adapters.driven.db.orm_models import AuthorModel
from ....ports.driven.services.author_service import AuthorService
from ....ports.driving.author_dto import AuthorPatchDTO, AuthorReadDTO, AuthorWriteDTO


class AuthorController(Controller):
    path = "/db-example-alchemy/authors"
    return_dto = AuthorReadDTO

    @post("/", dto=AuthorWriteDTO, status_code=HTTP_201_CREATED)
    @inject
    async def create(
        self,
        data: DTOData[AuthorModel],
        svc: FromDishka[AuthorService],
    ) -> AuthorModel:
        return await svc.create(data.create_instance(), auto_commit=True)

    @post("/bulk", dto=AuthorWriteDTO, status_code=HTTP_201_CREATED)
    @inject
    async def bulk_create(
        self,
        data: list[AuthorModel],
        svc: FromDishka[AuthorService],
    ) -> Sequence[AuthorModel]:
        # For a collection, let the DTO decode the JSON array straight into
        # model instances (DTOData.create_instance() is single-only).
        return await svc.create_many(data, auto_commit=True)

    @get("/")
    @inject
    async def list_authors(
        self,
        svc: FromDishka[AuthorService],
        search: Annotated[str, Parameter(max_length=200)] = "",
        limit: Annotated[int, Parameter(ge=1, le=200)] = 50,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[AuthorModel]:
        filters: list = [OrderBy("name", "asc"), LimitOffset(limit=limit, offset=offset)]
        if search:
            filters.insert(0, SearchFilter(field_name="name", value=search, ignore_case=True))
        results, total = await svc.get_many_and_count(*filters)
        return OffsetPagination(items=list(results), total=total, limit=limit, offset=offset)

    @get("/{author_id:uuid}")
    @inject
    async def get_one(
        self,
        author_id: UUID,
        svc: FromDishka[AuthorService],
    ) -> AuthorModel:
        return await svc.get(author_id, load=[AuthorModel.books])

    @patch("/{author_id:uuid}", dto=AuthorPatchDTO)
    @inject
    async def update(
        self,
        author_id: UUID,
        data: DTOData[AuthorModel],
        svc: FromDishka[AuthorService],
    ) -> AuthorModel:
        return await svc.update(data, item_id=author_id, auto_commit=True)

    @delete("/{author_id:uuid}", status_code=HTTP_204_NO_CONTENT)
    @inject
    async def remove(
        self,
        author_id: UUID,
        svc: FromDishka[AuthorService],
    ) -> None:
        await svc.delete(author_id, auto_commit=True)
