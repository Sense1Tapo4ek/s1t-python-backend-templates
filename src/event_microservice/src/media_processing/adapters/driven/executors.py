import hashlib
import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


def build_thread_pool(size: int) -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=size, thread_name_prefix="mp-thread")


def build_process_pool(size: int) -> ProcessPoolExecutor:
    # 'spawn', not the Linux default 'fork': forking a multi-threaded async worker
    # can inherit a held lock (redis pool, structlog) and deadlock the child.
    return ProcessPoolExecutor(max_workers=size, mp_context=multiprocessing.get_context("spawn"))


def plagiarism_blocking(video_id: str, work_seconds: float) -> str:
    """Stand-in for a blocking call that cannot be awaited (sync driver, C extension).

    Dispatched to a thread so the event loop is not stalled. GIL release is a
    bonus, not the reason -- the reason is that the call blocks its OS thread.
    """
    time.sleep(work_seconds)
    return hashlib.sha256(video_id.encode()).hexdigest()


def transcode_cpu(video_id: str, iterations: int) -> int:
    """Stand-in for CPU-bound work; dispatched to a process pool to bypass the GIL.

    A thread would not help here: the GIL serializes Python bytecode, so true
    parallelism needs a separate process. video_id is unused (a real encoder
    would read the source) but kept for call-site symmetry with the others.
    """
    total = 0
    for i in range(iterations):
        total += i * i
    return total
