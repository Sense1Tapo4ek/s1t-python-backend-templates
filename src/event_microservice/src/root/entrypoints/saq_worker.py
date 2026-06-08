from typing import Any

from saq import Queue

from root.config import RootConfig

_config = RootConfig()
_queue = Queue.from_url(_config.valkey_url)

# Slice 2 fills `functions` with the 3 SAQ jobs and adds startup/shutdown hooks
# that build and own the thread/process pools.
settings: dict[str, Any] = {
    "queue": _queue,
    "functions": [],
}
