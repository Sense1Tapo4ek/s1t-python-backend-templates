import asyncpg

from ...domain import Video, VideoStatus


def to_domain(row: asyncpg.Record) -> Video:
    return Video.reconstitute(
        id=row["id"],
        source_key=row["source_key"],
        status=VideoStatus(row["status"]),
        uploaded_at=row["uploaded_at"],
    )
