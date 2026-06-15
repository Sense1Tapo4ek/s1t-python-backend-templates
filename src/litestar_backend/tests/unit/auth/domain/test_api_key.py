from datetime import UTC, datetime
from uuid import uuid4

from auth.domain import (
    API_KEY_PREFIX,
    ApiKeyRecord,
    generate_api_key,
    hash_api_key,
)
from shared.domain.auth import Role


def test_generate_has_prefix_and_matching_hash() -> None:
    gen = generate_api_key()
    assert gen.plaintext.startswith(API_KEY_PREFIX)
    assert gen.key_hash == hash_api_key(gen.plaintext)
    assert len(gen.key_hash) == 64  # sha256 hex


def test_generate_is_unique() -> None:
    assert generate_api_key().plaintext != generate_api_key().plaintext


def test_hash_is_deterministic_and_hex() -> None:
    h = hash_api_key("ak_example")
    assert h == hash_api_key("ak_example")
    assert all(c in "0123456789abcdef" for c in h)


def test_record_is_frozen() -> None:
    rec = ApiKeyRecord(
        id=uuid4(), name="ci", role=Role.ADMIN, created_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert rec.role == Role.ADMIN
    try:
        rec.name = "x"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("ApiKeyRecord must be frozen")
