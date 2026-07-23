from datetime import UTC, datetime
from uuid import uuid4

import pytest

from auth.app import ApiKeyNotFound, GenerateApiKeyUC, ListApiKeysUC, RevokeApiKeyUC
from auth.domain import API_KEY_PREFIX, ApiKeyRecord
from shared.domain.auth import Role


class _Repo:
    def __init__(self, *, records=None, delete_result=True) -> None:
        self.records = records or []
        self.created: list[tuple[str, str, Role]] = []
        self._delete_result = delete_result
        self.deleted: list = []

    async def find_active_by_hash(self, key_hash):  # pragma: no cover
        return None

    async def create(self, *, key_hash, name, role):
        self.created.append((key_hash, name, role))
        return uuid4()

    async def list_active(self):
        return self.records

    async def soft_delete(self, api_key_id):
        self.deleted.append(api_key_id)
        return self._delete_result


@pytest.mark.asyncio
async def test_generate_returns_plaintext_once_and_stores_hash() -> None:
    """Given a name, When generating, Then a prefixed plaintext is returned and only the hash is stored."""
    repo = _Repo()
    uc = GenerateApiKeyUC(_repo=repo)
    _api_key_id, plaintext = await uc(name="ci", role=Role.ADMIN)
    assert plaintext.startswith(API_KEY_PREFIX)
    assert len(repo.created) == 1
    stored_hash, stored_name, stored_role = repo.created[0]
    assert stored_name == "ci" and stored_role == Role.ADMIN
    assert stored_hash != plaintext  # only the hash is persisted


@pytest.mark.asyncio
async def test_list_returns_records() -> None:
    rec = ApiKeyRecord(
        id=uuid4(), name="ci", role=Role.ADMIN, created_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    uc = ListApiKeysUC(_repo=_Repo(records=[rec]))
    assert await uc() == [rec]


@pytest.mark.asyncio
async def test_revoke_existing_returns_none() -> None:
    repo = _Repo(delete_result=True)
    uc = RevokeApiKeyUC(_repo=repo)
    key_id = uuid4()
    await uc(key_id)
    assert repo.deleted == [key_id]


@pytest.mark.asyncio
async def test_revoke_unknown_raises_not_found() -> None:
    uc = RevokeApiKeyUC(_repo=_Repo(delete_result=False))
    with pytest.raises(ApiKeyNotFound):
        await uc(uuid4())
