from datetime import UTC, datetime

from auth.adapters.driven.jwt_codec import JwtCodec, build_jwt_key
from auth.domain import TokenType
from auth.ports.driven import JwtService
from shared.domain.auth import Role


class _FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


def _service(secret: str | None, now: datetime) -> JwtService:
    codec = JwtCodec(_key=build_jwt_key(secret))
    return JwtService(
        _codec=codec,
        _clock=_FixedClock(now),
        _issuer="test-iss",
        _access_ttl=900,
        _refresh_ttl=1_209_600,
    )


def test_issue_then_verify_access_roundtrip() -> None:
    """Given an enabled service, When issuing then verifying the access token, Then role survives."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    svc = _service("topsecret", now)

    pair = svc.issue_pair(role=Role.ADMIN)

    assert pair is not None
    assert pair.expires_in == 900
    vt = svc.verify(pair.access, expected_type=TokenType.ACCESS)
    assert vt is not None
    assert vt.role == Role.ADMIN
    assert isinstance(vt.jti, str) and len(vt.jti) > 0


def test_access_token_rejected_as_refresh() -> None:
    """Given an access token, When verifying it as REFRESH, Then None."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    svc = _service("topsecret", now)
    pair = svc.issue_pair(role=Role.ADMIN)
    assert pair is not None
    assert svc.verify(pair.access, expected_type=TokenType.REFRESH) is None


def test_wrong_secret_fails_verification() -> None:
    """Given a token signed with secret A, When verified with secret B, Then None."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    pair = _service("secret-a", now).issue_pair(role=Role.ADMIN)
    assert pair is not None
    assert _service("secret-b", now).verify(pair.access) is None


def test_expired_token_fails_verification() -> None:
    """Given an access token, When verified 1h later, Then None (expired)."""
    issued = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    pair = _service("topsecret", issued).issue_pair(role=Role.ADMIN)
    assert pair is not None
    later = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)  # +1h > 900s access ttl
    assert _service("topsecret", later).verify(pair.access) is None


def test_issuer_mismatch_fails_verification() -> None:
    """Given a token from iss 'test-iss', When verified by a service with a different iss, Then None."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    pair = _service("topsecret", now).issue_pair(role=Role.ADMIN)
    assert pair is not None
    other = JwtService(
        _codec=JwtCodec(_key=build_jwt_key("topsecret")),
        _clock=_FixedClock(now),
        _issuer="other-iss",
        _access_ttl=900,
        _refresh_ttl=1_209_600,
    )
    assert other.verify(pair.access) is None


def test_disabled_service_returns_none() -> None:
    """Given no secret, When issuing or verifying, Then None (JWT disabled)."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    svc = _service(None, now)
    assert svc.issue_pair(role=Role.ADMIN) is None
    assert svc.verify("a.b.c") is None


def test_tampered_payload_fails_verification() -> None:
    """Given a token with a flipped payload char, When verified, Then None."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    svc = _service("topsecret", now)
    pair = svc.issue_pair(role=Role.ADMIN)
    assert pair is not None
    head, payload, sig = pair.access.split(".")
    tampered = f"{head}.{payload[:-1]}{'A' if payload[-1] != 'A' else 'B'}.{sig}"
    assert svc.verify(tampered) is None


def test_alg_none_token_is_rejected_without_raising() -> None:
    """Given a hand-crafted alg=none token, When verifying, Then None (no exception)."""
    import base64
    import json

    def _b64(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    now = datetime(2026, 1, 1, tzinfo=UTC)
    svc = _service("topsecret", now)
    header = _b64({"alg": "none", "typ": "JWT"})
    payload = _b64(
        {"iss": "test-iss", "role": "admin", "type": "access", "jti": "x", "exp": 9999999999}
    )
    forged = f"{header}.{payload}."
    assert svc.verify(forged) is None


def test_garbage_two_dot_string_is_rejected() -> None:
    """Given a non-JWT string with two dots, When verifying, Then None (no exception)."""
    now = datetime(2026, 1, 1, tzinfo=UTC)
    svc = _service("topsecret", now)
    assert svc.verify("not.a.jwt") is None
