"""Unit tests for TraceIdMiddleware inbound resolution + response echo."""

from unittest.mock import AsyncMock

import pytest

from shared.adapters.middleware.trace_middleware import TraceIdMiddleware


def _scope(*, headers: list[tuple[bytes, bytes]] | None = None) -> dict:
    return {"type": "http", "headers": headers or []}


async def _drain(mw: TraceIdMiddleware, scope: dict) -> str | None:
    """Run the middleware and return the echoed x-trace-id response header."""

    echoed: dict[str, str | None] = {"trace_id": None}

    async def inner(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def send(message):
        if message["type"] == "http.response.start":
            for name, value in message.get("headers", []):
                if name == b"x-trace-id":
                    echoed["trace_id"] = value.decode("ascii")

    mw._app = inner
    await mw(scope, AsyncMock(), send)
    return echoed["trace_id"]


@pytest.mark.asyncio
async def test_inbound_x_trace_id_is_honored_and_echoed() -> None:
    """
    Given an inbound X-Trace-Id header,
    When the middleware runs,
    Then that id is echoed on the response.
    """
    mw = TraceIdMiddleware(AsyncMock())
    echoed = await _drain(mw, _scope(headers=[(b"x-trace-id", b"trace-abc")]))
    assert echoed == "trace-abc"


@pytest.mark.asyncio
async def test_inbound_x_request_id_alias_is_honored_and_echoed() -> None:
    """
    Given an inbound X-Request-Id header (no X-Trace-Id),
    When the middleware runs,
    Then the request id is honored and echoed as X-Trace-Id.
    """
    mw = TraceIdMiddleware(AsyncMock())
    echoed = await _drain(mw, _scope(headers=[(b"X-Request-ID", b"req-xyz")]))
    assert echoed == "req-xyz"


@pytest.mark.asyncio
async def test_x_trace_id_takes_precedence_over_x_request_id() -> None:
    """
    Given both X-Trace-Id and X-Request-Id inbound,
    When the middleware runs,
    Then X-Trace-Id wins.
    """
    mw = TraceIdMiddleware(AsyncMock())
    echoed = await _drain(
        mw,
        _scope(headers=[(b"x-request-id", b"req-xyz"), (b"x-trace-id", b"trace-abc")]),
    )
    assert echoed == "trace-abc"


@pytest.mark.asyncio
async def test_generated_id_when_no_inbound_header() -> None:
    """
    Given no inbound trace/request id,
    When the middleware runs,
    Then a 16-char id is generated and echoed.
    """
    mw = TraceIdMiddleware(AsyncMock())
    echoed = await _drain(mw, _scope())
    assert echoed is not None
    assert len(echoed) == 16


@pytest.mark.asyncio
async def test_non_http_scope_passes_through() -> None:
    inner = AsyncMock()
    mw = TraceIdMiddleware(inner)
    await mw({"type": "lifespan"}, AsyncMock(), AsyncMock())
    inner.assert_awaited_once()
