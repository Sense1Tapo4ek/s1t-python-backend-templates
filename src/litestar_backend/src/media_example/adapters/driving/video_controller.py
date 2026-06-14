from typing import Annotated

from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get, post
from litestar.exceptions import ValidationException
from litestar.params import Parameter
from litestar.status_codes import HTTP_202_ACCEPTED
from prometheus_client import Counter

from shared.adapters.openapi import error_responses

from ...ports.driving import (
    MediaFacade,
    UploadVideoRequest,
    VideoModel,
    VideoPage,
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
    ) -> VideoPage:
        after = None
        if cursor is not None:
            try:
                after = decode_cursor(cursor)
            except ValueError as exc:
                raise ValidationException(detail="invalid cursor") from exc
        return await facade.list_page(after, limit)
