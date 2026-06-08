from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from ...orm_models import AuthorModel


class AuthorRepository(SQLAlchemyAsyncRepository[AuthorModel]):
    model_type = AuthorModel
