from advanced_alchemy.extensions.litestar.dto import SQLAlchemyDTO, SQLAlchemyDTOConfig

from ...adapters.driven.db.orm_models import BookModel


class BookReadDTO(SQLAlchemyDTO[BookModel]):
    config = SQLAlchemyDTOConfig(exclude={"created_at", "updated_at", "author"})


class BookWriteDTO(SQLAlchemyDTO[BookModel]):
    config = SQLAlchemyDTOConfig(exclude={"id", "created_at", "updated_at", "author"})
