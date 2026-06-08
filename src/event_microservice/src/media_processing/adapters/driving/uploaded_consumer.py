import msgspec
import structlog
from faststream.redis import RedisMessage, RedisRouter, StreamSub

from ...ports.driving import MediaProcessingFacade, VideoUploadedSchema

VIDEO_UPLOADED_STREAM = "video_uploaded"
CONSUMER_GROUP = "media_processing"

_log = structlog.get_logger("media_processing.consumer")
router = RedisRouter()
_state: dict[str, MediaProcessingFacade] = {}


def bind_facade(facade: MediaProcessingFacade) -> None:
    _state["facade"] = facade


async def handle_uploaded(payload: str | bytes, facade: MediaProcessingFacade) -> None:
    event = msgspec.json.decode(payload, type=VideoUploadedSchema)
    _log.info("video_uploaded received", video_id=str(event.video_id), event_id=str(event.event_id))
    await facade.on_uploaded(event.video_id)


@router.subscriber(stream=StreamSub(VIDEO_UPLOADED_STREAM, group=CONSUMER_GROUP, consumer=CONSUMER_GROUP))
async def on_video_uploaded(body: dict[str, str], msg: RedisMessage) -> None:
    await handle_uploaded(body["payload"], _state["facade"])
    await msg.ack()
