from typing import Annotated

from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get, post
from litestar.params import Parameter
from litestar.status_codes import HTTP_202_ACCEPTED
from prometheus_client import Counter

from shared.adapters.openapi import error_responses

from ...ports.driving import MediaFacade, UploadVideoRequest, VideoModel, VideoReadDTO

VIDEOS_UPLOADED = Counter("videos_uploaded", "Total videos uploaded")


class VideoController(Controller):
    path = "/videos"
    tags = ["media"]  # noqa: RUF012
    return_dto = VideoReadDTO

    @post(
        "/",
        status_code=HTTP_202_ACCEPTED,
        summary="Upload a video",
        responses=error_responses(400, 503),
    )
    @inject
    async def upload(self, data: UploadVideoRequest, facade: FromDishka[MediaFacade]) -> VideoModel:
        result = await facade.upload(data)
        VIDEOS_UPLOADED.inc()
        return result

    @get("/", summary="List recent videos", responses=error_responses(503))
    @inject
    async def list_recent(
        self,
        facade: FromDishka[MediaFacade],
        limit: Annotated[int, Parameter(ge=1, le=200)] = 50,
    ) -> list[VideoModel]:
        return await facade.list_recent(limit)
