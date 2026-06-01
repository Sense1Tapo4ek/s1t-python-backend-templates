from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from ....adapters.driven.db.orm_models import AuthorModel  # noqa: TID — driven ports may import adapters/driven


class AuthorRepository(SQLAlchemyAsyncRepository[AuthorModel]):
    model_type = AuthorModel
