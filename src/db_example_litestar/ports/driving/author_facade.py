from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from advanced_alchemy.filters import LimitOffset, OrderBy, SearchFilter

from ...domain import AuthorModel

# Hybrid context: the facade holds the advanced-alchemy service directly -- the
# one deliberate driving->driven crossing (ADR 0014), so the same CRUD is
# callable from code, not only over HTTP. Do NOT copy into a strict context.
from ..driven.services.author_service import AuthorService


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthorFacade:
    _service: AuthorService

    async def create(self, author: AuthorModel) -> AuthorModel:
        return await self._service.create(author, auto_commit=True)

    async def create_many(self, authors: Sequence[AuthorModel]) -> Sequence[AuthorModel]:
        return await self._service.create_many(list(authors), auto_commit=True)

    async def list(
        self, *, search: str = "", limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[AuthorModel], int]:
        filters: list[Any] = [OrderBy("name", "asc"), LimitOffset(limit=limit, offset=offset)]
        if search:
            filters.insert(0, SearchFilter(field_name="name", value=search, ignore_case=True))
        return await self._service.get_many_and_count(*filters)

    async def get(self, author_id: UUID) -> AuthorModel:
        return await self._service.get(author_id, load=[AuthorModel.books])

    async def update(self, author_id: UUID, changes: Mapping[str, Any]) -> AuthorModel:
        return await self._service.update(dict(changes), item_id=author_id, auto_commit=True)

    async def delete(self, author_id: UUID) -> None:
        await self._service.delete(author_id, auto_commit=True)
