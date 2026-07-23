from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from auth.ports.driven import SqlApiKeyRepo
from shared.adapters.driven.postgres import build_engine, build_sessionmaker, run_migrations
from shared.domain.auth import Role
from shared.generics.config import PROJECT_ROOT

_SCHEMA = "auth"
_MIGRATIONS_DIR = str(PROJECT_ROOT / "migrations" / "auth")


@pytest_asyncio.fixture(scope="module")
async def _auth_migrated(pg_dsn: str) -> None:
    yoyo_url = pg_dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    await run_migrations(yoyo_url, _MIGRATIONS_DIR)


@pytest_asyncio.fixture
async def sessionmaker(pg_dsn: str, _auth_migrated: None) -> AsyncIterator[async_sessionmaker]:
    alchemy_url = pg_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine: AsyncEngine = build_engine(alchemy_url, _SCHEMA, observe=False)
    try:
        yield build_sessionmaker(engine)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
class TestSqlApiKeyRepo:
    async def test_create_then_find_by_hash(self, sessionmaker: async_sessionmaker) -> None:
        """
        Given a created key,
        When finding by its hash,
        Then the record returns with its role.
        """
        repo = SqlApiKeyRepo(_sessionmaker=sessionmaker)
        # Unique per run: the Docker gate hits the persistent compose DB, so a
        # fixed hash would collide with rows left by previous runs.
        key_hash = f"hash-create-{uuid4()}"
        key_id = await repo.create(key_hash=key_hash, name="ci", role=Role.ADMIN)
        found = await repo.find_active_by_hash(key_hash)
        assert found is not None
        assert found.id == key_id and found.role == Role.ADMIN and found.name == "ci"

    async def test_unknown_hash_is_none(self, sessionmaker: async_sessionmaker) -> None:
        """
        Given no matching key,
        When finding by hash,
        Then None.
        """
        repo = SqlApiKeyRepo(_sessionmaker=sessionmaker)
        assert await repo.find_active_by_hash("nope-unknown-hash") is None

    async def test_soft_delete_hides_from_find_and_list(
        self, sessionmaker: async_sessionmaker
    ) -> None:
        """
        Given a key,
        When soft-deleted,
        Then find/list no longer return it and re-delete is False.
        """
        repo = SqlApiKeyRepo(_sessionmaker=sessionmaker)
        key_hash = f"hash-del-{uuid4()}"
        key_id = await repo.create(key_hash=key_hash, name="temp", role=Role.ADMIN)
        assert await repo.soft_delete(key_id) is True
        assert await repo.find_active_by_hash(key_hash) is None
        assert all(r.id != key_id for r in await repo.list_active())
        assert await repo.soft_delete(key_id) is False

    async def test_soft_delete_unknown_is_false(self, sessionmaker: async_sessionmaker) -> None:
        """
        Given an unknown id,
        When soft-deleting,
        Then False.
        """
        repo = SqlApiKeyRepo(_sessionmaker=sessionmaker)
        assert await repo.soft_delete(uuid4()) is False
