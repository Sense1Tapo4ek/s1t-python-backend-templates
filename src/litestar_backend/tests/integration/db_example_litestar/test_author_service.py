import pytest
import pytest_asyncio
from advanced_alchemy.base import UUIDAuditBase
from advanced_alchemy.filters import (
    LimitOffset,
    SearchFilter,
)
from sqlalchemy.ext.asyncio import async_sessionmaker

from db_example_litestar.ports.driven.services.author_service import AuthorService
from db_example_litestar.ports.orm_models import AuthorModel, BookModel
from shared.adapters.driven.postgres import build_engine, build_sessionmaker

_SCHEMA = "db_example_litestar"


@pytest_asyncio.fixture
async def sm(pg_dsn: str):
    alchemy_url = pg_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = build_engine(alchemy_url, _SCHEMA)
    async with engine.begin() as conn:
        await conn.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{_SCHEMA}"')
        await conn.run_sync(UUIDAuditBase.metadata.create_all)
    yield build_sessionmaker(engine)
    # Clean slate for the next test: drop+recreate the schema's tables.
    async with engine.begin() as conn:
        await conn.run_sync(UUIDAuditBase.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_search_paginate(sm: async_sessionmaker) -> None:
    async with sm() as session:
        svc = AuthorService(session=session)
        await svc.create_many(
            [AuthorModel(name="Stephen King"), AuthorModel(name="Jane Austen")],
            auto_commit=True,
        )
        results, total = await svc.get_many_and_count(
            SearchFilter(field_name="name", value="king", ignore_case=True),
            LimitOffset(limit=10, offset=0),
        )
        assert total == 1
        assert results[0].name == "Stephen King"


@pytest.mark.asyncio
async def test_eager_load_books(sm: async_sessionmaker) -> None:
    author_id = None
    async with sm() as session:
        svc = AuthorService(session=session)
        author = await svc.create(
            AuthorModel(name="Tolkien", books=[BookModel(title="LOTR")]), auto_commit=True
        )
        author_id = author.id

    # Fresh session to ensure eager-load works from cold state.
    async with sm() as session:
        svc = AuthorService(session=session)
        loaded = await svc.get(author_id, load=[AuthorModel.books])
        assert len(loaded.books) == 1
        assert loaded.books[0].title == "LOTR"
