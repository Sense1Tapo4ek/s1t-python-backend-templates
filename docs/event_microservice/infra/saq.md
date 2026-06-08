# SAQ (async job queue)

Version: saq (Valkey/Redis-backed). The worker runs via
`saq root.entrypoints.saq_worker.settings`.

`settings` = `{queue, functions=[stt, plagiarism, transcode], concurrency,
startup, shutdown}`. The `startup` hook builds the Dishka container + facade and
the thread/process pools, storing them in the SAQ `ctx`; `shutdown` tears them
down (`wait=True`) and closes the container. Jobs are enqueued by name
(`SaqJobQueue.enqueue(kind.value, video_id=...)`); each job's `__name__` equals
its `JobKind` value.

Testing: `Worker(..., burst=True, dequeue_timeout=1.0)` drains all queued jobs
in-process and exits -- used by the integration and e2e tests. Run:
`docker compose up event_microservice_worker`.
