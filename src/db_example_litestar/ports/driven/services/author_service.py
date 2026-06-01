from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from ....adapters.driven.db.orm_models import AuthorModel
from ..repos.author_repo import AuthorRepository


class AuthorService(SQLAlchemyAsyncRepositoryService[AuthorModel]):
    repository_type = AuthorRepository
