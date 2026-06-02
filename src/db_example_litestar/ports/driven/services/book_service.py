from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from ...orm_models import BookModel
from ..repos.book_repo import BookRepository


class BookService(SQLAlchemyAsyncRepositoryService[BookModel]):
    repository_type = BookRepository
