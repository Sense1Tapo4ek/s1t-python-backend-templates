# Delivery guarantees

How the media pipeline behaves under failure and redelivery. Audience: contributor.
The pipeline is **at-least-once end-to-end**; every consuming step is idempotent or
tolerates duplicates, so the system converges.

## Matrix

| Hop | Guarantee | Mechanism | Backed by |
|:---|:---|:---|:---|
| Outbox -> stream (backend) | at-least-once | the relay re-reads unsent rows until the broker accepts | `litestar_backend` outbox-relay tests |
| Stream -> consumer | at-least-once | a failed handler leaves the message un-acked; FastStream redelivers | `test_handle_uploaded` (ack on poison pill, raise on transient) |
| Consumer processing | **idempotent** | `event_id` inbox (`seen` / `mark_processed`), marked AFTER fan-out | `test_redelivery_idempotent`, `test_valkey_inbox_store` |
| Job enqueue | at-least-once | SAQ retries; a redelivered upload re-enqueues | `test_saq_job_queue` |
| Job join | **idempotent** | set-based distinct-kind count; re-adding a kind holds the count | `test_valkey_join_store` |
| `video_processing_started` / `_processed` | at-least-once | published on fan-out / join completion; consumer status machine dedups | flow tests |
| `video_processing_failed` | at-most-once | best-effort: a publish error is logged and swallowed | `OnJobFailedUC` flow test |

## Why mark-after-success

The inbox is marked only after fan-out + `publish_started` succeed. A failure before
that leaves the event unmarked and the inbound message un-acked, so FastStream
redelivers and the event reprocesses -- at-least-once is preserved, and the duplicate
fan-out is absorbed by the idempotent job join. Marking *before* processing would be
at-most-once (a crash mid-fan-out would lose the remaining jobs).

## Not a distributed lock

The inbox is not a mutex: two concurrent redeliveries of one event can both observe
`seen() == False` and both fan out. That is safe -- the join store converges. The
inbox's job is to skip re-doing an already-completed event, not to serialise.

## TTL

`MEDIA_PROCESSING_INBOX_TTL_SECONDS` (default 86400) bounds dedup memory. An event
redelivered after the window reprocesses; the join store still de-duplicates the
re-enqueued jobs.
