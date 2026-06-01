from advanced_alchemy.extensions.litestar.dto import SQLAlchemyDTO
from litestar.dto import DTOConfig

from ...adapters.driven.db.orm_models import BookModel


class BookReadDTO(SQLAlchemyDTO[BookModel]):
    config = DTOConfig(exclude={"created_at", "updated_at", "author"})


class BookWriteDTO(SQLAlchemyDTO[BookModel]):
    config = DTOConfig(exclude={"id", "created_at", "updated_at", "author"})
