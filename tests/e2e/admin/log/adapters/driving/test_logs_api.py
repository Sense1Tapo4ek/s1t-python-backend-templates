import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from litestar import Litestar
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)
from litestar.testing import TestClient

from _e2e_constants import E2E_ADMIN_TOKEN
from root.entrypoints.api import create_app

LINES = [
    {"timestamp": "2026-05-31T10:00:00Z", "level": "info", "logger": "root", "event": "boot", "context": {"pid": 1}},
    {"timestamp": "2026-05-31T10:00:01Z", "level": "warning", "logger": "auth", "event": "login slow", "context": {"ms": 900}},
    {"timestamp": "2026-05-31T10:00:02Z", "level": "error", "logger": "auth", "event": "login failed", "context": {"user": "x"}},
]


def _seed(tmp_path: Path) -> Path:
    log_file = tmp_path / "app.jsonl"
    log_file.write_text("".join(json.dumps(line) + "\n" for line in LINES), encoding="utf-8")
    return log_file


def _make_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Litestar:
    log_file = _seed(tmp_path)
    monkeypatch.setenv("APP_NAME", "litestar-base")
    monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
    # AdminLogConfig uses env_prefix="LOG_", so field `file_path` binds to
    # LOG_FILE_PATH (prefix + field name).
    monkeypatch.setenv("LOG_FILE_PATH", str(log_file))
    monkeypatch.setenv("LOG_TAIL_LINES", "2")
    monkeypatch.setenv("LOG_LOAD_MORE_LINES", "2")
    # The app's own structlog handler writes to LOG_FILE_PATH (writer == reader
    # file). Left enabled, lifespan startup lines append to the seeded file and
    # displace the tail window. These tests exercise the read path, not the
    # app's emission, so the file-handler reconfigure is stubbed out to keep the
    # seed pristine.
    monkeypatch.setattr("root.entrypoints.api.configure_structlog", lambda **_: None)
    # DI warms inside the TestClient lifespan; env is set above.
    return create_app()


class TestLogTailPage:
    def test_tail_returns_entries_and_cursor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, auth_headers: dict[str, str]
    ) -> None:
        """
        Given a seeded JSONL log file with three lines and tail size 2,
        When GET /api/v1/admin/logs/,
        Then the last two lines (chronological) and a non-null cursor return.
        """
        app = _make_app(tmp_path, monkeypatch)

        with TestClient(app=app) as client:
            res = client.get("/api/v1/admin/logs/", headers=auth_headers)

        assert res.status_code == HTTP_200_OK
        body = res.json()
        assert [e["event"] for e in body["entries"]] == ["login slow", "login failed"]
        assert body["cursor"] is not None

    def test_tail_requires_admin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given no Authorization header,
        When GET /api/v1/admin/logs/,
        Then the ADMIN guard rejects with 401.
        """
        app = _make_app(tmp_path, monkeypatch)

        with TestClient(app=app, raise_server_exceptions=False) as client:
            res = client.get("/api/v1/admin/logs/")

        assert res.status_code == HTTP_401_UNAUTHORIZED


class TestLogOlder:
    def test_older_paginates_backwards(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, auth_headers: dict[str, str]
    ) -> None:
        """
        Given the tail cursor from the first page,
        When GET /api/v1/admin/logs/older?cursor=<cursor>,
        Then the line before the tail window returns.
        """
        app = _make_app(tmp_path, monkeypatch)

        with TestClient(app=app) as client:
            page = client.get("/api/v1/admin/logs/", headers=auth_headers).json()
            cursor = page["cursor"]
            res = client.get(
                "/api/v1/admin/logs/older", params={"cursor": cursor}, headers=auth_headers
            )

        assert res.status_code == HTTP_200_OK
        body = res.json()
        assert [e["event"] for e in body["entries"]] == ["boot"]


async def _capture_response_start(
    app: Any, log_file: Path, token: str
) -> tuple[int, dict[str, str]]:
    """Drive the SSE endpoint at the ASGI layer and capture its start frame.

    The endpoint returns an infinite poll generator; Litestar (and the
    httpx-backed TestClient) only flush `http.response.start` once the
    generator yields its first frame, and the test transport buffers the
    body — so `client.stream` would block forever waiting for completion.
    Driving the ASGI callable directly lets us read the status + headers
    off the first `http.response.start` message and cancel immediately. A
    background appender writes a fresh line so the tail-follow generator
    yields (it starts at EOF), triggering the flush.
    """
    lifespan_done = asyncio.Event()
    lifespan_stop = asyncio.Event()

    async def lifespan_recv() -> dict[str, str]:
        if not lifespan_done.is_set():
            lifespan_done.set()
            return {"type": "lifespan.startup"}
        await lifespan_stop.wait()
        return {"type": "lifespan.shutdown"}

    async def lifespan_send(_message: dict[str, Any]) -> None:
        return None

    lifespan_task = asyncio.create_task(
        app({"type": "lifespan"}, lifespan_recv, lifespan_send)
    )
    # Let startup (DI graph, metrics) settle before issuing the request.
    await asyncio.sleep(0.5)

    captured: dict[str, Any] = {}
    started = asyncio.Event()

    async def append_loop() -> None:
        for index in range(60):
            await asyncio.sleep(0.05)
            with log_file.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {"timestamp": "x", "level": "info", "logger": "r", "event": f"live{index}"}
                    )
                    + "\n"
                )

    async def request_recv() -> dict[str, str]:
        await started.wait()
        return {"type": "http.disconnect"}

    async def request_send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
            captured["headers"] = {
                key.decode(): value.decode() for key, value in message["headers"]
            }
            started.set()

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/admin/logs/stream",
        "raw_path": b"/api/v1/admin/logs/stream",
        "query_string": b"",
        "headers": [
            (b"authorization", f"Bearer {token}".encode()),
            (b"host", b"test"),
        ],
        "scheme": "http",
        "server": ("test", 80),
        "client": ("testclient", 1),
        "http_version": "1.1",
        "root_path": "",
    }

    appender = asyncio.create_task(append_loop())
    request_task = asyncio.create_task(app(scope, request_recv, request_send))
    try:
        await asyncio.wait_for(started.wait(), timeout=10)
    finally:
        appender.cancel()
        request_task.cancel()
        lifespan_stop.set()
        await asyncio.gather(
            appender, request_task, lifespan_task, return_exceptions=True
        )

    return captured["status"], captured["headers"]


class TestLogStream:
    @pytest.mark.asyncio
    async def test_stream_opens_as_sse(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given the stream endpoint,
        When GET /api/v1/admin/logs/stream,
        Then it returns an SSE response with no-cache headers.
        """
        log_file = _seed(tmp_path)
        monkeypatch.setenv("APP_NAME", "litestar-base")
        monkeypatch.setenv("VOLUME_PATH", str(tmp_path))
        monkeypatch.setenv("LOG_FILE_PATH", str(log_file))
        monkeypatch.setenv("LOG_FOLLOW_POLL_MS", "50")
        monkeypatch.setattr(
            "root.entrypoints.api.configure_structlog", lambda **_: None
        )
        app = create_app()

        status, headers = await _capture_response_start(
            app, log_file, E2E_ADMIN_TOKEN
        )

        assert status == HTTP_200_OK
        assert headers["content-type"].startswith("text/event-stream")
        assert headers["cache-control"] == "no-cache"


class TestLogExport:
    def test_export_ndjson_streams_raw_lines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, auth_headers: dict[str, str]
    ) -> None:
        """
        Given a seeded file,
        When GET /api/v1/admin/logs/export/?format=ndjson,
        Then the raw JSONL lines stream back as a download.
        """
        app = _make_app(tmp_path, monkeypatch)

        with TestClient(app=app) as client:
            res = client.get(
                "/api/v1/admin/logs/export/", params={"format": "ndjson"}, headers=auth_headers
            )

        assert res.status_code == HTTP_200_OK
        assert res.headers["content-type"].startswith("application/x-ndjson")
        assert "logs.ndjson" in res.headers["content-disposition"]
        lines = [json.loads(line) for line in res.text.splitlines() if line]
        assert [e["event"] for e in lines] == ["boot", "login slow", "login failed"]

    def test_export_csv_has_header(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, auth_headers: dict[str, str]
    ) -> None:
        """
        Given a seeded file,
        When GET /api/v1/admin/logs/export/?format=csv,
        Then the CSV header lists the promoted columns.
        """
        app = _make_app(tmp_path, monkeypatch)

        with TestClient(app=app) as client:
            res = client.get(
                "/api/v1/admin/logs/export/", params={"format": "csv"}, headers=auth_headers
            )

        assert res.status_code == HTTP_200_OK
        assert res.text.startswith("timestamp,level,logger,event")

    def test_export_unknown_format_returns_400(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, auth_headers: dict[str, str]
    ) -> None:
        """
        Given an unsupported format,
        When GET /api/v1/admin/logs/export/?format=xml,
        Then the request is rejected with 400.
        """
        app = _make_app(tmp_path, monkeypatch)

        with TestClient(app=app, raise_server_exceptions=False) as client:
            res = client.get(
                "/api/v1/admin/logs/export/", params={"format": "xml"}, headers=auth_headers
            )

        assert res.status_code == HTTP_400_BAD_REQUEST
