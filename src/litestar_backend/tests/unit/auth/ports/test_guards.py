"""Unit tests for require_role guard."""

from unittest.mock import MagicMock

import pytest
from litestar.exceptions import NotAuthorizedException, PermissionDeniedException

from auth.ports.driving import require_role
from shared.domain.auth import Principal, Role


def _connection(user: Principal | None) -> MagicMock:
    conn = MagicMock()
    conn.user = user
    return conn


class TestRequireRoleGuard:
    def test_admin_principal_passes(self) -> None:
        guard = require_role(Role.ADMIN)
        guard(_connection(Principal(role=Role.ADMIN, token_id="x")), MagicMock())

    def test_unknown_role_raises_unauthorized(self) -> None:
        guard = require_role(Role.ADMIN)
        with pytest.raises(NotAuthorizedException):
            guard(
                _connection(Principal(role=Role.UNKNOWN, token_id="anonymous")),
                MagicMock(),
            )

    def test_missing_user_raises_unauthorized(self) -> None:
        guard = require_role(Role.ADMIN)
        conn = MagicMock()
        del conn.user  # ensure getattr returns None default
        with pytest.raises(NotAuthorizedException):
            guard(conn, MagicMock())

    def test_authenticated_but_wrong_role_raises_forbidden(self) -> None:
        # Simulate a future role by using an unrelated value.
        # We can't add roles dynamically; use UNKNOWN-vs-ADMIN pair already covered.
        # This test documents intent: when more roles exist, mismatch → 403.
        guard = require_role(Role.UNKNOWN)
        with pytest.raises(PermissionDeniedException):
            guard(_connection(Principal(role=Role.ADMIN, token_id="x")), MagicMock())
