import hashlib
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


def build_thread_pool(size: int) -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=size, thread_name_prefix="mp-thread")


def build_process_pool(size: int) -> ProcessPoolExecutor:
    return ProcessPoolExecutor(max_workers=size)


def plagiarism_blocking(video_id: str, work_seconds: float) -> str:
    """Blocking / GIL-releasing stand-in run off the event loop in a thread."""
    time.sleep(work_seconds)
    return hashlib.sha256(video_id.encode()).hexdigest()


def transcode_cpu(video_id: str, iterations: int) -> int:
    """CPU-bound stand-in run in a separate process (true parallelism past the GIL)."""
    total = 0
    for i in range(iterations):
        total += i * i
    return total
