from uuid import UUID

from shared.generics.errors import NotFoundError


class VideoNotFound(NotFoundError):
    def __init__(self, video_id: UUID) -> None:
        self.video_id = video_id
        super().__init__(f"video {video_id} not found")
