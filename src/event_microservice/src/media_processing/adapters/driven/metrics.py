from prometheus_client import Counter, Histogram, start_http_server

EVENTS_RECEIVED = Counter(
    "media_processing_events_received_total",
    "video_uploaded events consumed from the stream",
)
JOBS_PROCESSED = Counter(
    "media_processing_jobs_processed_total",
    "SAQ jobs processed, by kind",
    ["kind"],
)
JOB_DURATION = Histogram(
    "media_processing_job_duration_seconds",
    "SAQ job wall-clock duration, by kind",
    ["kind"],
)

STATUS_EVENTS_PUBLISHED = Counter(
    "media_processing_status_events_published_total",
    "video_status return events published, by event type",
    ["event_type"],
)

_started = False


def start_metrics_server(port: int) -> None:
    # Idempotent: a second call in the same process (e.g. two burst workers in one
    # test run) is a no-op instead of an 'address already in use' bind error.
    global _started
    if _started:
        return
    start_http_server(port)
    _started = True
