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

from shared.adapters.openapi import error_responses

# Everything comes from ports/driving: the facade (CRUD entry point), the DTOs,
# and the AuthorModel (re-exported there from ports/orm_models, since
# SQLAlchemyDTO generics need the ORM type). Controllers stay within their layer.
from ...ports.driving import (
    AuthorFacade,
    AuthorModel,
    AuthorPatchDTO,
    AuthorReadDTO,
    AuthorWriteDTO,
)


class AuthorController(Controller):
    path = "/db-example-litestar/authors"
    tags = ["db_example (Alchemy)"]  # noqa: RUF012
    return_dto = AuthorReadDTO

    @post("/", dto=AuthorWriteDTO, status_code=HTTP_201_CREATED,
          summary="Create an author", responses=error_responses(400))
    @inject
    async def create(
        self,
        data: DTOData[AuthorModel],
        facade: FromDishka[AuthorFacade],
    ) -> AuthorModel:
        """Create a single author."""
        return await facade.create(data.create_instance())

    @post("/bulk", dto=AuthorWriteDTO, status_code=HTTP_201_CREATED,
          summary="Bulk-create authors", responses=error_responses(400))
    @inject
    async def bulk_create(
        self,
        data: list[AuthorModel],
        facade: FromDishka[AuthorFacade],
    ) -> Sequence[AuthorModel]:
        """Create multiple authors from a JSON array in one request."""
        # For a collection, let the DTO decode the JSON array straight into
        # model instances (DTOData.create_instance() is single-only).
        return await facade.create_many(data)

    @get("/", summary="List authors (paginated)")
    @inject
    async def list_authors(
        self,
        facade: FromDishka[AuthorFacade],
        search: Annotated[str, Parameter(max_length=200)] = "",
        limit: Annotated[int, Parameter(ge=1, le=200)] = 50,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[AuthorModel]:
        """Return a page of authors, optionally filtered by a name search."""
        results, total = await facade.list(search=search, limit=limit, offset=offset)
        return OffsetPagination(items=list(results), total=total, limit=limit, offset=offset)

    @get("/{author_id:uuid}", summary="Get an author by id", responses=error_responses(404))
    @inject
    async def get_one(
        self,
        author_id: UUID,
        facade: FromDishka[AuthorFacade],
    ) -> AuthorModel:
        """Fetch a single author by id."""
        return await facade.get(author_id)

    @patch("/{author_id:uuid}", dto=AuthorPatchDTO,
           summary="Update an author", responses=error_responses(400, 404))
    @inject
    async def update(
        self,
        author_id: UUID,
        data: DTOData[AuthorModel],
        facade: FromDishka[AuthorFacade],
    ) -> AuthorModel:
        """Partially update an author by id."""
        return await facade.update(author_id, data.as_builtins())

    @delete("/{author_id:uuid}", status_code=HTTP_204_NO_CONTENT,
            summary="Delete an author", responses=error_responses(404))
    @inject
    async def remove(
        self,
        author_id: UUID,
        facade: FromDishka[AuthorFacade],
    ) -> None:
        """Delete an author by id."""
        await facade.delete(author_id)
