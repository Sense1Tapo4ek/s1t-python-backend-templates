from dataclasses import FrozenInstanceError

import pytest

from shared.domain.auth import Principal, Role


class TestPrincipalImmutability:
    def test_principal_is_frozen(self) -> None:
        p = Principal(role=Role.ADMIN, token_id="abc12345")
        with pytest.raises(FrozenInstanceError):
            p.role = Role.ADMIN  # type: ignore[misc]

    def test_principal_equality_by_value(self) -> None:
        a = Principal(role=Role.ADMIN, token_id="abc12345")
        b = Principal(role=Role.ADMIN, token_id="abc12345")
        assert a == b

    def test_role_admin_value(self) -> None:
        assert Role.ADMIN.value == "admin"

    def test_role_unknown_value(self) -> None:
        """UNKNOWN is the default role for unauthenticated requests."""
        assert Role.UNKNOWN.value == "unknown"

    def test_unknown_principal_constructible(self) -> None:
        """Unauthenticated callers get a Principal(UNKNOWN, 'anonymous')."""
        p = Principal(role=Role.UNKNOWN, token_id="anonymous")
        assert p.role == Role.UNKNOWN
        assert p.token_id == "anonymous"
