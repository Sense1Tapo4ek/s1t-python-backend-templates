import socket

import msgspec
import structlog
from faststream import Context
from faststream.redis import RedisMessage, RedisRouter, StreamSub

from ...ports.driving import MediaProcessingFacade, VideoUploadedSchema
from ..driven.metrics import EVENTS_RECEIVED

VIDEO_UPLOADED_STREAM = "video_uploaded"
CONSUMER_GROUP = "media_processing"
_CONSUMER = f"{CONSUMER_GROUP}-{socket.gethostname()}"

_log = structlog.get_logger("media_processing.consumer")
router = RedisRouter()


async def handle_uploaded(payload: str | bytes, facade: MediaProcessingFacade) -> None:
    event = msgspec.json.decode(payload, type=VideoUploadedSchema)
    EVENTS_RECEIVED.inc()
    _log.info("video_uploaded received", video_id=str(event.video_id), event_id=str(event.event_id))
    await facade.on_uploaded(event.video_id)


@router.subscriber(
    stream=StreamSub(VIDEO_UPLOADED_STREAM, group=CONSUMER_GROUP, consumer=_CONSUMER)
)
async def on_video_uploaded(
    body: dict[str, str],
    msg: RedisMessage,
    facade: MediaProcessingFacade = Context("facade"),
) -> None:
    try:
        await handle_uploaded(body["payload"], facade)
    except msgspec.MsgspecError:
        # Poison pill: a malformed payload never decodes -- log and ack so it does
        # not redeliver forever. Transient failures (PortError) propagate and stay
        # un-acked for redelivery. (event_id dedup is deferred; see
        # docs/contract/video_uploaded.md.)
        _log.warning("video_uploaded malformed payload dropped", raw=str(body)[:200])
    await msg.ack()
