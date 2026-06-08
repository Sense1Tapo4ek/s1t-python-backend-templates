# SAQ (async job queue)

Version: saq (Valkey/Redis-backed). The worker runs via
`saq root.entrypoints.saq_worker.settings`.

`settings` = `{queue, functions=[stt, plagiarism, transcode], concurrency,
startup, shutdown, after_process}`.

## Lifecycle hooks

- `startup`: builds the Dishka container + facade; starts the Prometheus
  metrics server (`cfg.metrics_port`); creates thread and process pools.
  Everything is stored in the SAQ `ctx` dict.
- `shutdown`: shuts down both pools (`wait=True`) and closes the Dishka
  container.
- `after_process`: inspects `ctx["exception"]`; if set, logs the failure at
  ERROR level with `job.function` and the error string. This is the single
  point for job-failure observability.

## Job enqueueing

Jobs are enqueued with both `retries` and `timeout` sourced from config
(`job_retries`, `job_timeout_seconds`):

```python
await queue.enqueue(kind.value, video_id=..., retries=retries, timeout=timeout)
```

## Two Queue instances (by design)

The consumer entrypoint and the SAQ worker entrypoint each construct their own
`Queue.from_url(valkey_url)` instance pointing at the same Valkey backend.
The consumer enqueues; the worker dequeues. Using separate instances avoids
cross-entrypoint state sharing and keeps each process self-contained.

## Process pool start method

The process pool uses the `spawn` start method explicitly
(`mp_context=multiprocessing.get_context("spawn")`). Rationale: forking a
multi-threaded async worker can inherit a held lock (redis pool, structlog)
and deadlock the child process. `spawn` starts a clean interpreter.

## Metrics server

A Prometheus HTTP server runs on port 9100 inside the container. Docker Compose
maps this to host port **9102** for the worker service. The server is
idempotent: a second call in the same process (e.g. two burst workers in a test)
is a no-op.

Testing: `Worker(..., burst=True, dequeue_timeout=1.0)` drains all queued jobs
in-process and exits -- used by the integration and e2e tests. Run:
`docker compose up event_microservice_worker`.
