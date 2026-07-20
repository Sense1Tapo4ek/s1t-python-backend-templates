from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from auth.app import (
    DeactivateUserUC,
    JwtDisabledError,
    ListUsersUC,
    LoginUserUC,
    RegisterUserUC,
    UserNotFound,
)
from auth.domain import TokenPair, UserRecord
from shared.domain.auth import Role

_NOW = datetime(2026, 7, 21, tzinfo=UTC)


def _user(email: str = "alice@example.com") -> UserRecord:
    return UserRecord(id=uuid4(), email=email, role=Role.USER, created_at=_NOW)


class _Hasher:
    def __init__(self, *, matches: bool = True) -> None:
        self._matches = matches
        self.verified: list[tuple[str, str]] = []

    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        self.verified.append((password, password_hash))
        return self._matches and password_hash == f"hashed:{password}"

    def dummy_hash(self) -> str:
        return "hashed:dummy"


class _Users:
    def __init__(self, *, user: UserRecord | None = None, password_hash: str = "") -> None:
        self._user = user
        self._hash = password_hash
        self.registered: list[tuple[str, str, Role]] = []
        self.deleted: list[UUID] = []
        self.delete_result = True

    async def register(self, *, email: str, password_hash: str, role: Role) -> UserRecord:
        self.registered.append((email, password_hash, role))
        return _user(email)

    async def find_credentials_by_email(self, email: str):
        return (self._user, self._hash) if self._user is not None else None

    async def is_active(self, user_id: UUID) -> bool:
        return True

    async def list_page(self, after, limit):
        return [self._user] if self._user else []

    async def soft_delete(self, user_id: UUID) -> bool:
        self.deleted.append(user_id)
        return self.delete_result


class _Jwt:
    def __init__(self, *, pair: TokenPair | None) -> None:
        self._pair = pair
        self.issued: list[tuple[Role, str | None]] = []

    def issue_pair(self, *, role: Role, subject: str | None = None) -> TokenPair | None:
        self.issued.append((role, subject))
        return self._pair

    def verify(self, token, *, expected_type=None):
        return None


@pytest.mark.asyncio
async def test_register_normalizes_email_and_hashes() -> None:
    """Given a cased email, When registering, Then the repo receives the
    normalized email, the argon2 hash, and Role.USER."""
    users = _Users()
    uc = RegisterUserUC(_users=users, _hasher=_Hasher())

    await uc(email="  Alice@Example.COM ", password="s3cret-pass")

    assert users.registered == [("alice@example.com", "hashed:s3cret-pass", Role.USER)]


@pytest.mark.asyncio
async def test_login_success_issues_user_bound_pair() -> None:
    """Given valid credentials, When logging in, Then the pair is minted with
    the user's id as subject."""
    user = _user()
    users = _Users(user=user, password_hash="hashed:s3cret-pass")
    jwt = _Jwt(pair=TokenPair(access="a", refresh="r", expires_in=900))
    uc = LoginUserUC(_users=users, _hasher=_Hasher(), _jwt=jwt)

    pair = await uc(email="Alice@example.com", password="s3cret-pass")

    assert pair is not None
    assert jwt.issued == [(Role.USER, str(user.id))]


@pytest.mark.asyncio
async def test_login_unknown_email_burns_dummy_hash_and_returns_none() -> None:
    """Given an unknown email, When logging in, Then None -- and the hasher
    still did one verify (timing equalization)."""
    hasher = _Hasher()
    uc = LoginUserUC(_users=_Users(), _hasher=hasher, _jwt=_Jwt(pair=None))

    assert await uc(email="ghost@example.com", password="whatever-pass") is None
    assert hasher.verified == [("whatever-pass", "hashed:dummy")]


@pytest.mark.asyncio
async def test_login_wrong_password_returns_none() -> None:
    """Given a wrong password, When logging in, Then None and no JWT minted."""
    users = _Users(user=_user(), password_hash="hashed:other-pass")
    jwt = _Jwt(pair=TokenPair(access="a", refresh="r", expires_in=900))
    uc = LoginUserUC(_users=users, _hasher=_Hasher(), _jwt=jwt)

    assert await uc(email="alice@example.com", password="s3cret-pass") is None
    assert jwt.issued == []


@pytest.mark.asyncio
async def test_login_with_jwt_disabled_raises() -> None:
    """Given valid credentials but no signing secret, When logging in,
    Then JwtDisabledError (503), never a silent None."""
    users = _Users(user=_user(), password_hash="hashed:s3cret-pass")
    uc = LoginUserUC(_users=users, _hasher=_Hasher(), _jwt=_Jwt(pair=None))

    with pytest.raises(JwtDisabledError):
        await uc(email="alice@example.com", password="s3cret-pass")


@pytest.mark.asyncio
async def test_list_users_delegates() -> None:
    """Given a repo page, When listing, Then it is returned as-is."""
    user = _user()
    uc = ListUsersUC(_users=_Users(user=user, password_hash="x"))

    assert await uc(None, 50) == [user]


@pytest.mark.asyncio
async def test_deactivate_unknown_user_raises_not_found() -> None:
    """Given no matching active user, When deactivating, Then UserNotFound (404)."""
    users = _Users()
    users.delete_result = False
    uc = DeactivateUserUC(_users=users)

    with pytest.raises(UserNotFound):
        await uc(uuid4())
