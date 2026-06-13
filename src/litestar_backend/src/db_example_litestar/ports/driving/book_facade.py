from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from advanced_alchemy.filters import LimitOffset, OrderBy

# Hybrid context -- facade holds the service (driving->driven, ADR 0014).
from ..driven.services.book_service import BookService
from ..orm_models import BookModel


@dataclass(frozen=True, slots=True, kw_only=True)
class BookFacade:
    """Public CRUD API of the db_example_litestar context for the Book aggregate.

    Single internal actor: the HTTP controller. Each method wraps one
    advanced-alchemy service call, commits eagerly (auto_commit), and returns
    the ORM model. A foreign-key violation on an unknown author_id surfaces as
    SQLAlchemy IntegrityError, which is unmapped and reaches the fallback
    handler as a 500 (a strict context would catch and translate it).
    """

    _service: BookService

    async def create(self, book: BookModel) -> BookModel:
        """Persist one book and commit. Returns the stored model."""
        return await self._service.create(book, auto_commit=True)

    async def list(self, *, limit: int = 50, offset: int = 0) -> tuple[Sequence[BookModel], int]:
        """Page books ordered by title. Returns the page slice and the total count."""
        filters: list[Any] = [OrderBy("title", "asc"), LimitOffset(limit=limit, offset=offset)]
        return await self._service.get_many_and_count(*filters)
