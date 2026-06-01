from advanced_alchemy.extensions.litestar.dto import SQLAlchemyDTO
from litestar.dto import DTOConfig

from ...adapters.driven.db.orm_models import AuthorModel


class AuthorReadDTO(SQLAlchemyDTO[AuthorModel]):
    config = DTOConfig(max_nested_depth=1)


class AuthorWriteDTO(SQLAlchemyDTO[AuthorModel]):
    config = DTOConfig(exclude={"id", "created_at", "updated_at", "books"})


class AuthorPatchDTO(SQLAlchemyDTO[AuthorModel]):
    config = DTOConfig(exclude={"id", "created_at", "updated_at", "books"}, partial=True)
