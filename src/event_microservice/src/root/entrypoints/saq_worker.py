from typing import Any

from media_processing.adapters.driven.saq_setup import build_queue, shutdown, startup
from media_processing.adapters.driving import plagiarism, stt, transcode
from media_processing.config import MediaProcessingConfig

_config = MediaProcessingConfig()

settings: dict[str, Any] = {
    "queue": build_queue(),
    "functions": [stt, plagiarism, transcode],
    "concurrency": _config.worker_concurrency,
    "startup": startup,
    "shutdown": shutdown,
}
