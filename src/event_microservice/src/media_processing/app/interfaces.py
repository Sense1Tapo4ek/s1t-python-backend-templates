from typing import Protocol
from uuid import UUID

from ..domain import JobKind


class IJobQueue(Protocol):
    async def enqueue(self, video_id: UUID, kind: JobKind) -> None:
        """Submit one processing job for a video to the durable queue.

        Called once per JobKind during fan-out (3 calls per uploaded video).
        Enqueue is durable (survives a worker restart) but NOT idempotent: a
        second call for the same (video_id, kind) enqueues a second job. At-least-
        once delivery means the consumer-side join must tolerate re-runs.

        Raises:
            PortError: the queue backend is unreachable or rejected the job.
        """
        ...


class IJoinStore(Protocol):
    async def add(self, video_id: UUID, kind: JobKind) -> int:
        """Record that `kind` finished for `video_id`; return the distinct-kind count.

        Idempotent: re-adding the same kind (at-least-once redelivery) does not
        change the count. Each call refreshes the key's TTL so a slow final job
        cannot let a partially-complete join expire. The returned count is how the
        caller detects completion (count == fan_out).

        Raises:
            PortError: the store backend is unreachable.
        """
        ...

    async def clear(self, video_id: UUID) -> None:
        """Delete the join record for `video_id`, called once on completion.

        Safe to call on a missing key (no-op). After clear, a late redelivered job
        re-creates the key with a single member; the TTL bounds that orphan.

        Raises:
            PortError: the store backend is unreachable.
        """
        ...
