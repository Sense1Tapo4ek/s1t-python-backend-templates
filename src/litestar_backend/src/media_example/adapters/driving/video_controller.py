from typing import Annotated
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, delete, get, post
from litestar.exceptions import ValidationException
from litestar.params import Parameter
from litestar.status_codes import HTTP_200_OK, HTTP_202_ACCEPTED
from prometheus_client import Counter

from shared.adapters.openapi import error_responses

from ...ports.driving import (
    MediaFacade,
    Page,
    UploadVideoRequest,
    VideoModel,
    VideoReadDTO,
    decode_cursor,
)

VIDEOS_UPLOADED = Counter("videos_uploaded", "Total videos uploaded")


class VideoController(Controller):
    path = "/videos"
    tags = ["media"]  # noqa: RUF012

    @post(
        "/",
        status_code=HTTP_202_ACCEPTED,
        return_dto=VideoReadDTO,
        summary="Upload a video",
        responses=error_responses(400, 503),
    )
    @inject
    async def upload(self, data: UploadVideoRequest, facade: FromDishka[MediaFacade]) -> VideoModel:
        result = await facade.upload(data)
        VIDEOS_UPLOADED.inc()
        return result

    @get("/", summary="List videos (keyset)", responses=error_responses(400, 503))
    @inject
    async def list_videos(
        self,
        facade: FromDishka[MediaFacade],
        cursor: Annotated[str | None, Parameter(required=False)] = None,
        limit: Annotated[int, Parameter(ge=1, le=200)] = 50,
    ) -> Page[VideoModel]:
        after = None
        if cursor is not None:
            try:
                after = decode_cursor(cursor)
            except ValueError as exc:
                raise ValidationException(detail="invalid cursor") from exc
        return await facade.list_page(after, limit)

    @delete("/{video_id:uuid}", summary="Soft-delete a video", responses=error_responses(404, 503))
    @inject
    async def delete_video(self, video_id: UUID, facade: FromDishka[MediaFacade]) -> None:
        await facade.delete(video_id)

    @post(
        "/{video_id:uuid}/cancel",
        status_code=HTTP_200_OK,
        summary="Cancel a video (transition to FAILED)",
        responses=error_responses(404, 409, 503),
    )
    @inject
    async def cancel_video(self, video_id: UUID, facade: FromDishka[MediaFacade]) -> None:
        """Cancel a video by transitioning it to FAILED. Terminal videos (DONE/FAILED)
        yield 409 InvalidTransition; unknown ids yield 404. Cancel surfaces as `failed`
        on the SSE feed; a dedicated CANCELLED state is intentionally out of scope."""
        await facade.mark_failed(video_id)
