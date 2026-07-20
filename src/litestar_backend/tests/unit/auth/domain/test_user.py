from datetime import UTC, datetime
from uuid import uuid4

from auth.domain import EmailTakenError, UserRecord, normalize_email
from shared.domain.auth import Role
from shared.generics.errors import DomainError


def test_normalize_email_trims_and_lowercases() -> None:
    """Given a cased, padded email, When normalized, Then trimmed lowercase."""
    assert normalize_email("  Alice@Example.COM ") == "alice@example.com"


def test_normalize_email_is_idempotent() -> None:
    """Given an already-normal email, When normalized, Then unchanged."""
    assert normalize_email("bob@example.com") == "bob@example.com"


def test_email_taken_is_domain_error_with_context() -> None:
    """Given a taken email, When the error is built, Then it carries the email
    and maps into the DomainError branch (409)."""
    err = EmailTakenError("alice@example.com")
    assert isinstance(err, DomainError)
    assert err.email == "alice@example.com"


def test_user_record_is_frozen_value() -> None:
    """Given a record, When compared to an identical one, Then equal."""
    now = datetime(2026, 7, 21, tzinfo=UTC)
    uid = uuid4()
    a = UserRecord(id=uid, email="a@b.co", role=Role.USER, created_at=now)
    b = UserRecord(id=uid, email="a@b.co", role=Role.USER, created_at=now)
    assert a == b
