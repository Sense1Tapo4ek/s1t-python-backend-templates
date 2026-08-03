from typing import Annotated
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, Response, delete, get, post
from litestar.exceptions import ValidationException
from litestar.params import HeaderParameter, Parameter
from litestar.status_codes import HTTP_200_OK, HTTP_202_ACCEPTED
from prometheus_client import Counter

from shared.adapters.openapi import error_responses

from ...ports.driving import (
    IDEMPOTENCY_KEY_MAX_LENGTH,
    IDEMPOTENCY_REPLAYED_HEADER,
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
        responses=error_responses(400, 422, 503),
    )
    @inject
    async def upload(
        self,
        data: UploadVideoRequest,
        facade: FromDishka[MediaFacade],
        idempotency_key: Annotated[
            str | None,
            HeaderParameter(
                name="Idempotency-Key",
                required=False,
                min_length=1,
                max_length=IDEMPOTENCY_KEY_MAX_LENGTH,
                description=(
                    "Opaque client-chosen retry key. Repeating a request with the same "
                    "key returns the first result instead of creating a second video."
                ),
            ),
        ] = None,
    ) -> Response[VideoModel]:
        result = await facade.upload(data, idempotency_key)
        if not result.replayed:
            VIDEOS_UPLOADED.inc()
        return Response(
            content=result.video,
            status_code=HTTP_202_ACCEPTED,
            headers={IDEMPOTENCY_REPLAYED_HEADER: str(result.replayed).lower()}
            if idempotency_key is not None
            else {},
        )

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
