# media_processing

Audience: contributor working on the worker.

Consumes `video_uploaded` (Valkey Stream), fans 3 SAQ jobs per video, joins them
in Valkey. Two processes share one image: `consumer` (FastStream subscriber ->
`facade.on_uploaded` -> enqueue 3 jobs) and `saq_worker` (runs the jobs).

## Mental model

```
video_uploaded stream --> consumer.handle_uploaded --> facade.on_uploaded
                                                          --> enqueue stt|plagiarism|transcode
saq_worker: each job --> run via its model --> facade.complete_job --> SADD join:{video_id}
            3rd completion --> log "video processed" --> DEL join:{video_id}
```

## The three execution models

| Job | Model | Dispatch |
|:--|:--|:--|
| `stt` | async / I/O | `await asyncio.sleep(...)` (no executor) |
| `plagiarism` | thread pool | `run_in_executor(thread_pool, plagiarism_blocking, ...)` |
| `transcode` | process pool | `run_in_executor(process_pool, transcode_cpu, ...)` |

Pools are built once in the SAQ `startup` hook (`adapters/driven/saq_setup.py`),
stored in `ctx`, and shut down (`wait=True`) on worker stop. Process-pool work
functions are module-level (picklable).

## Public surface

- Inbound schema: `ports/driving/VideoUploadedSchema` (OWN; never imports the
  producer's integration event).
- Facade: `MediaProcessingFacade.on_uploaded(video_id)` / `.complete_job(video_id, kind)`.
- Config: `MEDIA_PROCESSING_` (`worker_concurrency`,
  `thread_pool_size`, `process_pool_size`, `fake_work_seconds`,
  `transcode_iterations`, `join_ttl_seconds`, `job_retries`,
  `job_timeout_seconds`, `metrics_port`).
- Metrics (Prometheus, port 9100 in-container):
  - `media_processing_events_received_total` -- events consumed from the stream.
  - `media_processing_jobs_processed_total{kind}` -- SAQ jobs completed, by kind.
  - `media_processing_job_duration_seconds{kind}` -- job wall-clock duration histogram.

## Invariants & gotchas

- **Fan-out is `len(JobKind)`**, wired directly in the provider -- it is derived
  from the domain enum, not a config knob. Add a `JobKind` member and the join
  threshold follows automatically.
- The SADD join is idempotent under SAQ at-least-once redelivery; a job rerun
  re-adds the same kind and SCARD is unchanged. No dedup table is needed --
  SADD already gives completion-level idempotency.
- Jobs retry up to `job_retries` times with a `job_timeout_seconds` deadline per
  attempt. Both values flow from config into `SaqJobQueue.enqueue`.
- A `join_ttl_seconds` TTL guards against a job that never completes.
- Status events published: `video_processing_started` after fan-out
  (OnVideoUploadedUC), `video_processed` before join clear (CompleteJobUC),
  `video_processing_failed` from the SAQ `after_process` hook on terminal
  failure. See [../../contract/video_status.md](../../contract/video_status.md).
- Wire contracts: [../../contract/video_uploaded.md](../../contract/video_uploaded.md) (inbound),
  [../../contract/video_status.md](../../contract/video_status.md) (outbound).
