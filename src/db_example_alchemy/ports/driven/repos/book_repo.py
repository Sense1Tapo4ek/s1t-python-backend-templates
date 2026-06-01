from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from ....adapters.driven.db.orm_models import BookModel  # noqa: TID — driven ports may import adapters/driven


class BookRepository(SQLAlchemyAsyncRepository[BookModel]):
    model_type = BookModel
