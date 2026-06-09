from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from advanced_alchemy.filters import LimitOffset, OrderBy, SearchFilter

# Hybrid context: the facade holds the advanced-alchemy service directly -- the
# one deliberate driving->driven crossing (ADR 0014), so the same CRUD is
# callable from code, not only over HTTP. Do NOT copy into a strict context.
from ..driven.services.author_service import AuthorService
from ..orm_models import AuthorModel


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthorFacade:
    """Public CRUD API of the db_example_litestar context for the Author aggregate.

    Single internal actor: the HTTP controller. Each method wraps one
    advanced-alchemy service call, commits eagerly (auto_commit), and returns
    the ORM model. advanced-alchemy's NotFoundError (missing id) propagates
    unchanged; the global exception handler maps it to 404.
    """

    _service: AuthorService

    async def create(self, author: AuthorModel) -> AuthorModel:
        """Persist one author and commit. Returns the stored model."""
        return await self._service.create(author, auto_commit=True)

    async def create_many(self, authors: Sequence[AuthorModel]) -> Sequence[AuthorModel]:
        """Persist a batch of authors in one commit. Returns the stored models."""
        return await self._service.create_many(list(authors), auto_commit=True)

    async def list(
        self, *, search: str = "", limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[AuthorModel], int]:
        """Page authors ordered by name; optional case-insensitive name search.

        Returns the page slice and the total count matching the filters.
        """
        filters: list[Any] = [OrderBy("name", "asc"), LimitOffset(limit=limit, offset=offset)]
        if search:
            filters.insert(0, SearchFilter(field_name="name", value=search, ignore_case=True))
        return await self._service.get_many_and_count(*filters)

    async def get(self, author_id: UUID) -> AuthorModel:
        """Fetch one author with books eager-loaded. Raises NotFoundError if absent."""
        return await self._service.get(author_id, load=[AuthorModel.books])

    async def update(self, author_id: UUID, changes: Mapping[str, Any]) -> AuthorModel:
        """Apply a partial update and commit. Raises NotFoundError if the id is absent."""
        return await self._service.update(dict(changes), item_id=author_id, auto_commit=True)

    async def delete(self, author_id: UUID) -> None:
        """Delete one author and commit. Raises NotFoundError if the id is absent."""
        await self._service.delete(author_id, auto_commit=True)
