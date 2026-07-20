from datetime import UTC, datetime
from uuid import uuid4

import msgspec
import pytest
import redis.asyncio as aioredis
from sqlalchemy import bindparam, text

from media_example.ports.driven.integration_events import (
    VIDEO_UPLOADED_STREAM,
    VideoUploadedIntegration,
)
from media_example.ports.driven.orm_models import OutboxRow
from shared.adapters.driven.outbox_relay import OutboxRelay
from shared.adapters.driven.postgres import build_engine, build_sessionmaker

_QUERY_SENT = text("SELECT id, sent_at FROM media.outbox_messages WHERE id IN :ids").bindparams(
    bindparam("ids", expanding=True)
)
_DELETE_OUTBOX = text("DELETE FROM media.outbox_messages WHERE id IN :ids").bindparams(
    bindparam("ids", expanding=True)
)


@pytest.mark.asyncio
async def test_drain_once_publishes_rows_to_stream(
    pg_dsn: str,
    valkey: aioredis.Redis,
    _migrated: None,
) -> None:
    """
    Given 2 outbox rows with known ids,
    When _drain_once() is called,
    Then 2 messages are published to the Valkey stream and sent_at is set.
    """
    # Arrange
    id_a = uuid4()
    id_b = uuid4()
    video_id = uuid4()
    source_key = "s3://bucket/relay-test.mp4"
    now = datetime.now(tz=UTC)

    payload_a = msgspec.json.encode(
        VideoUploadedIntegration(
            event_id=id_a,
            occurred_at=now,
            video_id=video_id,
            source_key=source_key,
            uploaded_at=now,
        )
    )
    payload_b = msgspec.json.encode(
        VideoUploadedIntegration(
            event_id=id_b,
            occurred_at=now,
            video_id=video_id,
            source_key=source_key,
            uploaded_at=now,
        )
    )

    alchemy_url = pg_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = build_engine(alchemy_url, "media")
    sm = build_sessionmaker(engine)
    try:
        async with sm() as s, s.begin():
            s.add(OutboxRow(id=id_a, event_type="video_uploaded", payload=payload_a))
            s.add(OutboxRow(id=id_b, event_type="video_uploaded", payload=payload_b))

        relay = OutboxRelay(
            _sessionmaker=sm,
            _valkey=valkey,
            _stream=VIDEO_UPLOADED_STREAM,
            _batch=10,
            _idle_sleep=0.1,
        )

        # Act
        published = await relay._drain_once()

        # Assert: count
        assert published >= 2

        # Assert: sent_at is set for our two rows
        async with sm() as s:
            rows = (await s.execute(_QUERY_SENT, {"ids": [id_a, id_b]})).mappings().all()
        row_map = {r["id"]: r["sent_at"] for r in rows}
        assert row_map[id_a] is not None, "id_a.sent_at must be set"
        assert row_map[id_b] is not None, "id_b.sent_at must be set"

        # Assert: stream has at least 2 entries
        stream_len = await valkey.xlen(VIDEO_UPLOADED_STREAM)
        assert stream_len >= 2

        # Assert: at least one stream entry decodes to the expected payload
        entries = await valkey.xrange(VIDEO_UPLOADED_STREAM) or []
        found = False
        for _entry_id, fields in entries:
            if fields is None:
                continue
            raw = fields.get("payload", "")
            if not raw:
                continue
            decoded = msgspec.json.decode(raw if isinstance(raw, bytes) else raw.encode())
            if decoded.get("video_id") == str(video_id):
                assert decoded["source_key"] == source_key
                found = True
                break
        assert found, "No stream entry contained the expected video_id"

    finally:
        # Critical cleanup: relay commits for real; delete our rows explicitly.
        async with sm() as s, s.begin():
            await s.execute(_DELETE_OUTBOX, {"ids": [id_a, id_b]})
        await engine.dispose()
        # valkey fixture flushdb on teardown -- no extra action needed here.
