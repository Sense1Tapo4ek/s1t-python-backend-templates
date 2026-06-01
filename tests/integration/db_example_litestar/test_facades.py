from pathlib import Path

import pytest
import pytest_asyncio
from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy.ext.asyncio import async_sessionmaker

from db_example_litestar.adapters.driven.db.engine import build_engine, build_sessionmaker
from db_example_litestar.adapters.driven.db.orm_models import AuthorModel, BookModel
from db_example_litestar.ports.driven.services.author_service import AuthorService
from db_example_litestar.ports.driven.services.book_service import BookService
from db_example_litestar.ports.driving import AuthorFacade, BookFacade


@pytest_asyncio.fixture
async def sm(tmp_path: Path):
    engine = build_engine(tmp_path / "a.db")
    async with engine.begin() as conn:
        await conn.run_sync(UUIDAuditBase.metadata.create_all)
    yield build_sessionmaker(engine)
    await engine.dispose()


@pytest.mark.asyncio
async def test_author_facade_full_crud_from_code(sm: async_sessionmaker) -> None:
    """
    Given the AuthorFacade wired over a real session,
    When CRUD is driven from code (no HTTP),
    Then create/list/search/get/update/delete all behave.
    """
    async with sm() as session:
        facade = AuthorFacade(_service=AuthorService(session=session))

        await facade.create_many([AuthorModel(name="Stephen King"), AuthorModel(name="Jane Austen")])

        results, total = await facade.list(search="king", limit=10, offset=0)
        assert total == 1
        author_id = results[0].id

        loaded = await facade.get(author_id)
        assert loaded.books == []

        updated = await facade.update(author_id, {"name": "Stephen Edwin King"})
        assert updated.name == "Stephen Edwin King"

        await facade.delete(author_id)
        _, total_after = await facade.list(limit=10, offset=0)
        assert total_after == 1


@pytest.mark.asyncio
async def test_book_facade_create_and_list_from_code(sm: async_sessionmaker) -> None:
    """
    Given AuthorFacade + BookFacade over a real session,
    When a book is created for an author from code,
    Then it is listed back.
    """
    async with sm() as session:
        author = await AuthorFacade(_service=AuthorService(session=session)).create(
            AuthorModel(name="Tolkien")
        )
        book_facade = BookFacade(_service=BookService(session=session))

        await book_facade.create(BookModel(title="LOTR", author_id=author.id))

        results, total = await book_facade.list(limit=10, offset=0)
        assert total == 1
        assert results[0].title == "LOTR"
