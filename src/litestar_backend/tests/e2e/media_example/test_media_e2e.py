import time

import pytest
import redis.asyncio as aioredis
from litestar.testing import TestClient


def test_upload_returns_202_pending(e2e_client: TestClient) -> None:
    """
    Given a valid upload request,
    When POST /videos is called,
    Then 202 is returned with status=pending and the echoed source_key.
    """
    # Arrange
    payload = {"source_key": "s3://bucket/a.mp4"}

    # Act
    resp = e2e_client.post("/videos", json=payload)

    # Assert
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert "id" in body
    assert body["source_key"] == "s3://bucket/a.mp4"


def test_list_includes_uploaded(e2e_client: TestClient) -> None:
    """
    Given a successfully uploaded video,
    When GET /videos is called,
    Then the response includes the uploaded video's id.
    """
    # Arrange
    upload_resp = e2e_client.post("/videos", json={"source_key": "s3://bucket/b.mp4"})
    assert upload_resp.status_code == 202
    video_id = upload_resp.json()["id"]

    # Act
    list_resp = e2e_client.get("/videos", params={"limit": 50})

    # Assert
    assert list_resp.status_code == 200
    ids = [v["id"] for v in list_resp.json()]
    assert video_id in ids


@pytest.mark.asyncio
async def test_outbox_drained_to_stream(
    e2e_client: TestClient, valkey: aioredis.Redis
) -> None:
    """
    Given an uploaded video (outbox row written in the same tx),
    When the background relay drains the outbox,
    Then at least one entry appears on the video_uploaded Valkey stream.

    Strategy: poll the live stream for up to 5 s (the relay sleeps ~0.5 s
    between drains). TestClient is synchronous, so time.sleep is used.
    """
    # Arrange
    resp = e2e_client.post("/videos", json={"source_key": "s3://bucket/c.mp4"})
    assert resp.status_code == 202

    # Act + Assert — poll until stream has at least one entry or timeout
    deadline = 5.0
    interval = 0.2
    elapsed = 0.0
    stream_len = 0
    while elapsed < deadline:
        stream_len = await valkey.xlen("video_uploaded")
        if stream_len >= 1:
            break
        time.sleep(interval)
        elapsed += interval

    assert stream_len >= 1, (
        f"Expected at least 1 entry in video_uploaded stream after {deadline}s; got {stream_len}"
    )


def test_feed_opens_stream(e2e_client: TestClient) -> None:
    """
    Given a running app with the ChannelsPlugin,
    When GET /videos/feed is opened as an SSE stream,
    Then HTTP 200 is returned with content-type text/event-stream.
    """
    # Act
    with e2e_client.stream("GET", "/videos/feed") as resp:
        # Assert — check headers immediately without consuming events
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
