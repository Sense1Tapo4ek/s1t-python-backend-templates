"""Unit tests for AccessLogMiddleware enrichment (C5)."""

from unittest.mock import AsyncMock, patch

import pytest

from shared.adapters.middleware.access_log_middleware import AccessLogMiddleware


def _scope(
    *,
    method: str = "GET",
    path: str = "/x",
    query: bytes = b"",
    client: tuple[str, int] | None = ("198.51.100.7", 1234),
    headers: list[tuple[bytes, bytes]] | None = None,
    user=None,
) -> dict:
    return {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query,
        "client": client,
        "headers": headers or [],
        "user": user,
    }


async def _drain(mw: AccessLogMiddleware, scope: dict) -> dict:
    """Run the middleware and return the captured info call kwargs."""
    async def inner(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    captured = {}

    def _info(event, **kwargs):
        captured["event"] = event
        captured.update(kwargs)

    with patch(
        "shared.adapters.middleware.access_log_middleware._logger.info",
        side_effect=_info,
    ):
        mw._app = inner
        await mw(scope, AsyncMock(), AsyncMock())

    return captured


@pytest.mark.asyncio
async def test_minimum_fields_present_for_anonymous_request() -> None:
    mw = AccessLogMiddleware(AsyncMock())
    info = await _drain(mw, _scope())

    assert info["event"] == "request"
    assert info["method"] == "GET"
    assert info["http_path"] == "/x"
    assert info["status"] == 200
    assert isinstance(info["duration_ms"], (int, float))
    assert info["client_ip"] == "198.51.100.7"
    assert info["user_agent"] is None
    assert info["user"] is None
    assert info["query"] is None


@pytest.mark.asyncio
async def test_query_string_captured() -> None:
    mw = AccessLogMiddleware(AsyncMock())
    info = await _drain(mw, _scope(query=b"foo=1&bar=baz"))
    assert info["query"] == "foo=1&bar=baz"


@pytest.mark.asyncio
async def test_user_agent_captured() -> None:
    mw = AccessLogMiddleware(AsyncMock())
    info = await _drain(
        mw,
        _scope(headers=[(b"user-agent", b"curl/8.1.0")]),
    )
    assert info["user_agent"] == "curl/8.1.0"


@pytest.mark.asyncio
async def test_x_forwarded_for_takes_precedence_over_socket_ip() -> None:
    """
    Given X-Forwarded-For with a chain of IPs,
    When access log fires,
    Then the leftmost IP wins (proxy convention).
    """
    mw = AccessLogMiddleware(AsyncMock())
    info = await _drain(
        mw,
        _scope(
            client=("10.0.0.1", 1),
            headers=[(b"x-forwarded-for", b"203.0.113.5, 10.0.0.1")],
        ),
    )
    assert info["client_ip"] == "203.0.113.5"


@pytest.mark.asyncio
async def test_user_token_id_pulled_from_principal() -> None:
    class _P:
        token_id = "abc12345"

    mw = AccessLogMiddleware(AsyncMock())
    info = await _drain(mw, _scope(user=_P()))
    assert info["user"] == "abc12345"


@pytest.mark.asyncio
async def test_client_ip_unknown_when_no_client_or_xff() -> None:
    mw = AccessLogMiddleware(AsyncMock())
    info = await _drain(mw, _scope(client=None))
    assert info["client_ip"] == "unknown"


@pytest.mark.asyncio
async def test_non_http_scope_passes_through_without_logging() -> None:
    inner = AsyncMock()
    mw = AccessLogMiddleware(inner)
    with patch(
        "shared.adapters.middleware.access_log_middleware._logger.info",
    ) as logger_info:
        await mw({"type": "lifespan"}, AsyncMock(), AsyncMock())
    inner.assert_awaited_once()
    logger_info.assert_not_called()
