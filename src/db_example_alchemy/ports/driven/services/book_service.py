from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from ....adapters.driven.db.orm_models import BookModel  # noqa: TID — driven ports may import adapters/driven
from ..repos.book_repo import BookRepository


class BookService(SQLAlchemyAsyncRepositoryService[BookModel]):
    repository_type = BookRepository
