from saq import Queue


def build_queue(url: str) -> Queue:
    return Queue.from_url(url)
