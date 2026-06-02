from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from ....domain import AuthorModel


class AuthorRepository(SQLAlchemyAsyncRepository[AuthorModel]):
    model_type = AuthorModel
