from litestar.testing import TestClient


def test_cancel_transitions_pending_video_to_failed(e2e_client: TestClient) -> None:
    """
    Given a freshly uploaded (PENDING) video,
    When POST /videos/{id}/cancel is called,
    Then 200 is returned and the video reports status=failed.
    """
    # Arrange
    video_id = e2e_client.post("/videos", json={"source_key": "s3://bucket/cancel.mp4"}).json()[
        "id"
    ]

    # Act
    resp = e2e_client.post(f"/videos/{video_id}/cancel")

    # Assert
    assert resp.status_code == 200
    items = e2e_client.get("/videos", params={"limit": 200}).json()["items"]
    match = next(v for v in items if v["id"] == video_id)
    assert match["status"] == "failed"


def test_cancel_terminal_video_returns_409(e2e_client: TestClient) -> None:
    """
    Given a video already cancelled (terminal FAILED),
    When POST /videos/{id}/cancel is called again,
    Then 409 problem+json with the invalid-transition type is returned.
    """
    # Arrange -- upload, then cancel once so the video is terminal.
    video_id = e2e_client.post("/videos", json={"source_key": "s3://bucket/cancel2.mp4"}).json()[
        "id"
    ]
    first = e2e_client.post(f"/videos/{video_id}/cancel")
    assert first.status_code == 200

    # Act -- second cancel on a terminal video.
    resp = e2e_client.post(f"/videos/{video_id}/cancel")

    # Assert
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["type"] == "urn:litestar-base:error:invalid-transition"


def test_cancel_unknown_video_returns_404(e2e_client: TestClient) -> None:
    """Given a valid-but-unknown uuid, When POST /videos/{id}/cancel, Then 404."""
    resp = e2e_client.post("/videos/00000000-0000-0000-0000-0000000000ff/cancel")
    assert resp.status_code == 404
