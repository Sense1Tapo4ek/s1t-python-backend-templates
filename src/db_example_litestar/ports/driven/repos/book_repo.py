from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from ....domain import BookModel


class BookRepository(SQLAlchemyAsyncRepository[BookModel]):
    model_type = BookModel
