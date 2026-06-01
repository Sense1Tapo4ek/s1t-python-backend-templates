from advanced_alchemy.filters import LimitOffset, OrderBy
from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get, post
from litestar.dto import DTOData
from litestar.pagination import OffsetPagination
from litestar.status_codes import HTTP_201_CREATED

from ....adapters.driven.db.orm_models import BookModel
from ....ports.driven.services.book_service import BookService
from ....ports.driving.book_dto import BookReadDTO, BookWriteDTO


class BookController(Controller):
    path = "/db-example-alchemy/books"
    return_dto = BookReadDTO

    @post("/", dto=BookWriteDTO, status_code=HTTP_201_CREATED)
    @inject
    async def create(
        self,
        data: DTOData[BookModel],
        svc: FromDishka[BookService],
    ) -> BookModel:
        return await svc.create(data.create_instance(), auto_commit=True)

    @get("/")
    @inject
    async def list_books(
        self,
        svc: FromDishka[BookService],
        limit: int = 50,
        offset: int = 0,
    ) -> OffsetPagination[BookModel]:
        filters: list = [OrderBy("title", "asc"), LimitOffset(limit=limit, offset=offset)]
        results, total = await svc.get_many_and_count(*filters)
        return OffsetPagination(items=list(results), total=total, limit=limit, offset=offset)
