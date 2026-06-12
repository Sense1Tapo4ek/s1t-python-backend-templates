# SAQ (async job queue)

Version: saq 0.26+ with the `web` extra (Valkey/Redis-backed). The worker runs
via `saq root.entrypoints.saq_worker.settings --web --port 8080`.

`settings` = `{queue, functions=[stt, plagiarism, transcode], concurrency,
startup, shutdown, after_process}`.

## Lifecycle hooks

- `startup`: builds the Dishka container + facade; starts the Prometheus
  metrics server (`cfg.metrics_port`); creates thread and process pools.
  Everything is stored in the SAQ `ctx` dict.
- `shutdown`: shuts down both pools (`wait=True`) and closes the Dishka
  container.
- `after_process`: inspects `ctx["exception"]`; if set, logs the failure at
  ERROR level with `job.function` and the error string. On terminal failure
  (`attempts >= retries`) it calls `facade.on_job_failed` -> publishes
  `video_processing_failed` (at-most-once) and clears the join store. This is
  the single point for job-failure observability and cleanup.

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

## Web panel (admin UI)

SAQ ships an aiohttp monitoring UI: queue stats, per-job detail, retry and
abort actions. Enabled by the `--web --port 8080` flags on the worker command;
Docker Compose maps it to host port **8081** -> `http://localhost:8081`.

- Requires the `saq[web]` dependency extra (aiohttp + aiohttp_basicauth) --
  already in `pyproject.toml`.
- Auth: HTTP Basic when the `AUTH_PASSWORD` env var is set (user defaults to
  `admin`, override via `AUTH_USER`). Compose feeds it from `SAQ_WEB_PASSWORD`
  in `.env`; empty means no auth -- dev only, never expose the port publicly
  without a password.
- The panel monitors the worker's own queue; to watch additional queues pass
  `--extra-web-settings <module.settings>`.

## Metrics server

A Prometheus HTTP server runs on port 9100 inside the container. Docker Compose
maps this to host port **9102** for the worker service. The server is
idempotent: a second call in the same process (e.g. two burst workers in a test)
is a no-op.

Testing: `Worker(..., burst=True, dequeue_timeout=1.0)` drains all queued jobs
in-process and exits -- used by the integration and e2e tests. Run:
`docker compose up event_microservice_worker`.
