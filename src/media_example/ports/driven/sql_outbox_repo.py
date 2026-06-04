from dataclasses import dataclass

import asyncpg

from shared.generics.errors import PortError

from ...app import IOutboxRepo
from ...domain import VideoUploaded
from .outbox_mappers import encode_payload, to_integration


@dataclass(slots=True, kw_only=True)
class SqlOutboxRepo(IOutboxRepo):
    _conn: asyncpg.Connection

    async def add(self, event: VideoUploaded) -> None:
        integration = to_integration(event)
        payload = encode_payload(integration)
        try:
            await self._conn.execute(
                """
                INSERT INTO outbox_messages (id, event_type, payload, created_at)
                VALUES ($1, $2, $3, now())
                """,
                integration.event_id,
                integration.event_type,
                payload,
            )
        except asyncpg.PostgresError as exc:
            raise PortError(f"add outbox message failed: {exc}") from exc
