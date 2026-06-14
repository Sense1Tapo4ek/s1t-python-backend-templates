import json
import time
from datetime import UTC, datetime
from uuid import uuid4

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
    ids = [v["id"] for v in list_resp.json()["items"]]
    assert video_id in ids


@pytest.mark.asyncio
async def test_outbox_drained_to_stream(e2e_client: TestClient, valkey: aioredis.Redis) -> None:
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

    # Act + Assert -- poll until stream has at least one entry or timeout
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
        # Assert -- check headers immediately without consuming events
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")


@pytest.mark.asyncio
async def test_status_events_drive_video_to_done(
    e2e_client: TestClient, valkey: aioredis.Redis
) -> None:
    """
    Given an uploaded video and worker-shaped status events on video_status,
    When the lifespan consumer processes them,
    Then GET /videos eventually reports the video as done.
    """
    # Arrange -- remove any leftover video_status entries from this session.
    # Deleting the stream also drops its consumer group, so this test exercises
    # the consumer's lazy NOGROUP re-create path in _claim_stale.
    await valkey.delete("video_status")

    resp = e2e_client.post("/videos", json={"source_key": "s3://bucket/d.mp4"})
    assert resp.status_code == 202
    video_id = resp.json()["id"]

    def entry(event_type: str) -> dict[str, str]:
        event_id = str(uuid4())
        payload = json.dumps(
            {
                "event_id": event_id,
                "event_type": event_type,
                "version": 1,
                "video_id": video_id,
                "occurred_at": datetime.now(UTC).isoformat(),
            }
        )
        return {"event_id": event_id, "event_type": event_type, "payload": payload}

    # Act -- simulate the worker's return events
    await valkey.xadd("video_status", entry("video_processing_started"))
    await valkey.xadd("video_status", entry("video_processed"))

    # Assert -- poll until the consumer applies both
    deadline, interval, elapsed = 15.0, 0.25, 0.0
    status = None
    while elapsed < deadline:
        videos = {
            v["id"]: v["status"]
            for v in e2e_client.get("/videos", params={"limit": 50}).json()["items"]
        }
        status = videos.get(video_id)
        if status == "done":
            break
        time.sleep(interval)
        elapsed += interval

    assert status == "done", f"video stayed in status={status!r} after {deadline}s"


def test_list_paginates_with_cursor(e2e_client: TestClient) -> None:
    """
    Given at least two uploaded videos,
    When paging with limit=1 and following next_cursor,
    Then the cursor walks to a distinct video id.
    """
    e2e_client.post("/videos", json={"source_key": "s3://bucket/p1.mp4"})
    e2e_client.post("/videos", json={"source_key": "s3://bucket/p2.mp4"})

    first = e2e_client.get("/videos", params={"limit": 1}).json()
    assert len(first["items"]) == 1
    assert first["next_cursor"] is not None

    second = e2e_client.get("/videos", params={"limit": 1, "cursor": first["next_cursor"]}).json()
    assert len(second["items"]) == 1
    assert first["items"][0]["id"] != second["items"][0]["id"]


def test_list_rejects_malformed_cursor(e2e_client: TestClient) -> None:
    """Given a malformed cursor, When GET /videos, Then 400."""
    resp = e2e_client.get("/videos", params={"cursor": "not-a-cursor"})
    assert resp.status_code == 400


def test_delete_soft_deletes_and_hides(e2e_client: TestClient) -> None:
    """
    Given an uploaded video,
    When DELETE /videos/{id} is called,
    Then it returns 204 and the video no longer appears in the list.
    """
    video_id = e2e_client.post("/videos", json={"source_key": "s3://bucket/del.mp4"}).json()["id"]

    resp = e2e_client.delete(f"/videos/{video_id}")

    assert resp.status_code == 204
    listed = e2e_client.get("/videos", params={"limit": 200}).json()["items"]
    assert video_id not in [v["id"] for v in listed]


def test_delete_unknown_returns_404(e2e_client: TestClient) -> None:
    """Given a random id, When DELETE /videos/{id}, Then 404."""
    resp = e2e_client.delete("/videos/00000000-0000-0000-0000-0000000000ff")
    assert resp.status_code == 404
