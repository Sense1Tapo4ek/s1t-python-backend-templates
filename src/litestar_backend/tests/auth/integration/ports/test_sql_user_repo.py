from collections.abc import AsyncIterator
from uuid import uuid4

import msgspec
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from auth.domain import EmailTakenError
from auth.ports.driven import SqlUserRepo
from shared.adapters.driven.clocks import SystemClock
from shared.adapters.driven.postgres import build_engine, build_sessionmaker, run_migrations
from shared.domain.auth import Role
from shared.generics.config import PROJECT_ROOT

_SCHEMA = "auth"
_MIGRATIONS_DIR = str(PROJECT_ROOT / "migrations" / "auth")


def _email() -> str:
    return f"user-{uuid4()}@example.com"


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


@pytest.fixture
def repo(sessionmaker: async_sessionmaker) -> SqlUserRepo:
    return SqlUserRepo(_sessionmaker=sessionmaker, _clock=SystemClock())


@pytest.mark.asyncio
class TestSqlUserRepo:
    async def test_register_writes_user_and_outbox_atomically(
        self, repo: SqlUserRepo, sessionmaker: async_sessionmaker
    ) -> None:
        """
        Given a registration,
        When it commits,
        Then the user row AND a user_registered outbox row exist, and the
        payload carries the user id without the email.
        """
        # Act
        user = await repo.register(email=_email(), password_hash="hashed", role=Role.USER)

        # Assert
        async with sessionmaker() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT event_type, payload FROM auth.outbox_messages om "
                        "WHERE (convert_from(om.payload, 'UTF8')::jsonb ->> 'user_id') = :uid"
                    ),
                    {"uid": str(user.id)},
                )
            ).one()
        assert row.event_type == "user_registered"
        payload = msgspec.json.decode(bytes(row.payload))
        assert payload["user_id"] == str(user.id)
        assert payload["role"] == "user"
        assert "email" not in payload
        assert await repo.is_active(user.id)

    async def test_duplicate_active_email_raises_email_taken(self, repo: SqlUserRepo) -> None:
        """
        Given a registered email,
        When registering it again,
        Then EmailTakenError.
        """
        email = _email()
        await repo.register(email=email, password_hash="h1", role=Role.USER)
        with pytest.raises(EmailTakenError):
            await repo.register(email=email, password_hash="h2", role=Role.USER)

    async def test_soft_delete_frees_email_and_deactivates(self, repo: SqlUserRepo) -> None:
        """
        Given a user,
        When soft-deleted,
        Then login lookup and is_active go empty, re-delete is False, and the
        email can be registered again (partial unique index).
        """
        email = _email()
        user = await repo.register(email=email, password_hash="h", role=Role.USER)

        assert await repo.soft_delete(user.id) is True
        assert await repo.find_credentials_by_email(email) is None
        assert await repo.is_active(user.id) is False
        assert await repo.soft_delete(user.id) is False

        again = await repo.register(email=email, password_hash="h2", role=Role.USER)
        assert again.id != user.id

    async def test_find_credentials_returns_record_and_hash(self, repo: SqlUserRepo) -> None:
        """
        Given a registered user,
        When looking up by email,
        Then (record, password_hash) round-trips.
        """
        email = _email()
        user = await repo.register(email=email, password_hash="the-hash", role=Role.USER)

        found = await repo.find_credentials_by_email(email)

        assert found is not None
        record, password_hash = found
        assert record.id == user.id and password_hash == "the-hash"

    async def test_list_page_keyset_walks_without_overlap(self, repo: SqlUserRepo) -> None:
        """
        Given 3 users,
        When paging with limit 2 then following the keyset,
        Then pages don't overlap and cover all 3.
        """
        created = [
            (await repo.register(email=_email(), password_hash="h", role=Role.USER)).id
            for _ in range(3)
        ]

        first = await repo.list_page(None, 2)
        assert len(first) == 2
        second = await repo.list_page((first[-1].created_at, first[-1].id), 2)

        ids = {u.id for u in first} | {u.id for u in second}
        assert set(created) <= ids
        assert {u.id for u in first} & {u.id for u in second} == set()
