from uuid import UUID

from shared.generics.errors import AppError, NotFoundError


class VideoNotFound(NotFoundError):
    def __init__(self, video_id: UUID) -> None:
        self.video_id = video_id
        super().__init__(f"video {video_id} not found")


class IdempotencyKeyReused(AppError):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"idempotency key {key} was already used with a different payload")
