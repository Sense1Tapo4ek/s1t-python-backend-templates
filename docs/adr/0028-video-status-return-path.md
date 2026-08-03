---
status: accepted
date: 2026-06-12
---
# 0028 - Return events on one direct-publish video_status stream

## Context
Phase C closes the pipeline loop: the worker must report
started/processed/failed back to media_example, which owns videos.status and
the browser SSE feed. The worker has no Postgres, so the outbox pattern used
on the forward path is unavailable.

## Decision
One Valkey Stream `video_status` carries all three event types (FIFO per
stream preserves started -> processed order per video). The worker publishes
with a direct XADD from a driven port; PortError propagates: a failed
`started` leaves the inbound `video_uploaded` message unacked (FastStream
redelivers it, re-running OnVideoUploadedUC), a failed `processed` fails the
SAQ job (SAQ retries it, re-running CompleteJobUC) -- effectively at-least-once
for both. The `failed` event fires from SAQ's after_process (not retried,
at-most-once, explicitly logged). The backend consumes with a hand-rolled
XREADGROUP lifespan task (per-process consumer name + XAUTOCLAIM adoption of
stale pending entries); duplicate deliveries die on the status machine's
InvalidTransition and are acked.

## Consequences
- + No new broker or table; idempotency needs no dedup store.
- + Teaching contrast: durable outbox (forward) vs direct publish (return).
- - A crash between XADD and job-ack can duplicate events (absorbed), and a
    lost failed event leaves a video in processing until manual action.

## Alternatives considered
- Two streams (started/processed separate) -- cross-stream ordering race.
- Outbox in the worker -- requires Postgres the service deliberately lacks.
- FastStream consumer in the backend -- second framework inside Litestar's
  lifespan for one stream; rejected.
