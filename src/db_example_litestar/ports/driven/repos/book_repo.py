from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from ...orm_models import BookModel


class BookRepository(SQLAlchemyAsyncRepository[BookModel]):
    model_type = BookModel
