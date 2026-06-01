from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from advanced_alchemy.filters import LimitOffset, OrderBy

# Hybrid context — see author_facade.py for the boundary note (ADR 0012).
from ...adapters.driven.db.orm_models import BookModel
from ..driven.services.book_service import BookService


@dataclass(frozen=True, slots=True, kw_only=True)
class BookFacade:
    _service: BookService

    async def create(self, book: BookModel) -> BookModel:
        return await self._service.create(book, auto_commit=True)

    async def list(
        self, *, limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[BookModel], int]:
        filters: list[Any] = [OrderBy("title", "asc"), LimitOffset(limit=limit, offset=offset)]
        return await self._service.get_many_and_count(*filters)
