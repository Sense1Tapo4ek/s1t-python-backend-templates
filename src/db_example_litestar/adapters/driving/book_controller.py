from typing import Annotated

from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get, post
from litestar.dto import DTOData
from litestar.pagination import OffsetPagination
from litestar.params import Parameter
from litestar.status_codes import HTTP_201_CREATED

from ...ports.driving import BookFacade, BookModel, BookReadDTO, BookWriteDTO


class BookController(Controller):
    path = "/db-example-litestar/books"
    return_dto = BookReadDTO

    @post("/", dto=BookWriteDTO, status_code=HTTP_201_CREATED)
    @inject
    async def create(
        self,
        data: DTOData[BookModel],
        facade: FromDishka[BookFacade],
    ) -> BookModel:
        return await facade.create(data.create_instance())

    @get("/")
    @inject
    async def list_books(
        self,
        facade: FromDishka[BookFacade],
        limit: Annotated[int, Parameter(ge=1, le=200)] = 50,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[BookModel]:
        results, total = await facade.list(limit=limit, offset=offset)
        return OffsetPagination(items=list(results), total=total, limit=limit, offset=offset)
