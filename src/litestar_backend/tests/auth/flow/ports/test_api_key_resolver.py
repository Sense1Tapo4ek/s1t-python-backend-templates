from datetime import UTC, datetime
from uuid import uuid4

import pytest

from auth.domain import ApiKeyRecord, hash_api_key
from auth.ports.driven import ApiKeyResolver
from shared.domain.auth import Role


class _FakeRepo:
    def __init__(self, record: ApiKeyRecord | None) -> None:
        self._record = record
        self.looked_up: list[str] = []

    async def find_active_by_hash(self, key_hash: str):
        self.looked_up.append(key_hash)
        return self._record

    async def create(self, *, key_hash, name, role):  # pragma: no cover
        raise NotImplementedError

    async def list_active(self):  # pragma: no cover
        return []

    async def soft_delete(self, api_key_id):  # pragma: no cover
        return False


def _record() -> ApiKeyRecord:
    return ApiKeyRecord(
        id=uuid4(), name="ci", role=Role.ADMIN, created_at=datetime(2026, 1, 1, tzinfo=UTC)
    )


@pytest.mark.asyncio
async def test_non_api_key_shape_is_skipped() -> None:
    """Given a token without the ak_ prefix, When resolving, Then the repo is never queried."""
    repo = _FakeRepo(_record())
    resolver = ApiKeyResolver(_repo=repo)
    assert await resolver.resolve("a.b.c") is None
    assert repo.looked_up == []


@pytest.mark.asyncio
async def test_valid_api_key_resolves_to_principal() -> None:
    """Given an active ak_ key, When resolving, Then an ADMIN principal is returned."""
    record = _record()
    repo = _FakeRepo(record)
    resolver = ApiKeyResolver(_repo=repo)
    principal = await resolver.resolve("ak_secret")
    assert principal is not None
    assert principal.role == Role.ADMIN
    assert repo.looked_up == [hash_api_key("ak_secret")]


@pytest.mark.asyncio
async def test_unknown_api_key_is_none() -> None:
    """Given an ak_ key not in the store, When resolving, Then None."""
    resolver = ApiKeyResolver(_repo=_FakeRepo(None))
    assert await resolver.resolve("ak_unknown") is None
