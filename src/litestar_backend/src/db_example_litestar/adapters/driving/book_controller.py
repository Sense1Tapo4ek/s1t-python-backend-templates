from typing import Annotated

from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get, post
from litestar.dto import DTOData
from litestar.pagination import OffsetPagination
from litestar.params import Parameter
from litestar.status_codes import HTTP_201_CREATED

from shared.adapters.openapi import error_responses

from ...ports.driving import BookFacade, BookModel, BookReadDTO, BookWriteDTO


class BookController(Controller):
    path = "/db-example-litestar/books"
    tags = ["db_example (Alchemy)"]  # noqa: RUF012
    return_dto = BookReadDTO

    @post(
        "/",
        dto=BookWriteDTO,
        status_code=HTTP_201_CREATED,
        summary="Create a book",
        responses=error_responses(400),
    )
    @inject
    async def create(
        self,
        data: DTOData[BookModel],
        facade: FromDishka[BookFacade],
    ) -> BookModel:
        """Create a single book."""
        return await facade.create(data.create_instance())

    @get("/", summary="List books (paginated)")
    @inject
    async def list_books(
        self,
        facade: FromDishka[BookFacade],
        limit: Annotated[int, Parameter(ge=1, le=200)] = 50,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[BookModel]:
        """Return a page of books with the total count for offset pagination."""
        results, total = await facade.list(limit=limit, offset=offset)
        return OffsetPagination(items=list(results), total=total, limit=limit, offset=offset)
