from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from ....adapters.driven.db.orm_models import BookModel


class BookRepository(SQLAlchemyAsyncRepository[BookModel]):
    model_type = BookModel
