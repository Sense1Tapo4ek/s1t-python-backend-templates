from uuid import uuid4

from litestar.testing import TestClient


def test_repeated_key_replays_the_first_response_byte_for_byte(e2e_client: TestClient) -> None:
    """
    Given an upload accepted under an Idempotency-Key,
    When the identical request is retried with that same key,
    Then the first response body comes back unchanged, flagged as a replay.
    """
    # Arrange
    key = str(uuid4())
    payload = {"source_key": "s3://bucket/idem.mp4", "document": {"content_type": "video/mp4"}}
    first = e2e_client.post("/videos", json=payload, headers={"Idempotency-Key": key})
    assert first.status_code == 202
    assert first.headers["Idempotency-Replayed"] == "false"

    # Act
    second = e2e_client.post("/videos", json=payload, headers={"Idempotency-Key": key})

    # Assert
    assert second.status_code == 202
    assert second.content == first.content
    assert second.headers["Idempotency-Replayed"] == "true"


def test_repeated_key_creates_only_one_video(e2e_client: TestClient) -> None:
    """
    Given an upload retried three times under one Idempotency-Key,
    When the video list is read,
    Then the source key appears exactly once.
    """
    # Arrange
    key = str(uuid4())
    source_key = f"s3://bucket/{uuid4()}.mp4"

    # Act
    for _ in range(3):
        resp = e2e_client.post(
            "/videos", json={"source_key": source_key}, headers={"Idempotency-Key": key}
        )
        assert resp.status_code == 202

    # Assert
    listed = e2e_client.get("/videos", params={"limit": 200}).json()["items"]
    assert [v["source_key"] for v in listed].count(source_key) == 1


def test_same_key_with_a_different_payload_is_422(e2e_client: TestClient) -> None:
    """
    Given a key already used for one payload,
    When a different payload is sent with that key,
    Then 422 is returned as an RFC 9457 problem instead of a wrong replay.
    """
    # Arrange
    key = str(uuid4())
    first = e2e_client.post(
        "/videos", json={"source_key": "s3://bucket/one.mp4"}, headers={"Idempotency-Key": key}
    )
    assert first.status_code == 202

    # Act
    resp = e2e_client.post(
        "/videos", json={"source_key": "s3://bucket/two.mp4"}, headers={"Idempotency-Key": key}
    )

    # Assert
    assert resp.status_code == 422
    body = resp.json()
    assert body["type"] == "urn:litestar-base:error:idempotency-key-reused"
    assert body["instance"] == "/videos"


def test_upload_without_the_header_keeps_creating_new_videos(e2e_client: TestClient) -> None:
    """
    Given no Idempotency-Key header,
    When the same payload is posted twice,
    Then two distinct videos are created and no replay header is sent.
    """
    # Arrange
    payload = {"source_key": "s3://bucket/no-key.mp4"}

    # Act
    first = e2e_client.post("/videos", json=payload)
    second = e2e_client.post("/videos", json=payload)

    # Assert
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] != second.json()["id"]
    assert "Idempotency-Replayed" not in first.headers


def test_blank_idempotency_key_is_rejected(e2e_client: TestClient) -> None:
    """
    Given an empty Idempotency-Key header,
    When an upload is posted,
    Then it is rejected as a validation error rather than silently ignored.
    """
    # Act
    resp = e2e_client.post(
        "/videos", json={"source_key": "s3://bucket/blank.mp4"}, headers={"Idempotency-Key": ""}
    )

    # Assert
    assert resp.status_code == 400
