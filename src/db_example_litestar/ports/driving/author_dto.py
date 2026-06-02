from advanced_alchemy.extensions.litestar.dto import SQLAlchemyDTO, SQLAlchemyDTOConfig

from ...domain import AuthorModel


class AuthorReadDTO(SQLAlchemyDTO[AuthorModel]):
    config = SQLAlchemyDTOConfig(max_nested_depth=1)


class AuthorWriteDTO(SQLAlchemyDTO[AuthorModel]):
    config = SQLAlchemyDTOConfig(exclude={"id", "created_at", "updated_at", "books"})


class AuthorPatchDTO(SQLAlchemyDTO[AuthorModel]):
    config = SQLAlchemyDTOConfig(exclude={"id", "created_at", "updated_at", "books"}, partial=True)
