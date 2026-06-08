# FastStream (Valkey Streams consumer)

Version: faststream[redis,cli] (CLI extra required -- the runtime CMD is
`faststream run root.entrypoints.consumer:app`).

Subscribes to the `video_uploaded` stream via a consumer group
(`StreamSub(..., group="media_processing")`), acks each message. The subscriber
in `media_processing/adapters/driving/uploaded_consumer.py` is a thin wrapper
over `handle_uploaded(payload, facade)` -- the testable seam. The facade is
resolved from the Dishka container in `app.on_startup` and bound before any
message is consumed.

Run: `docker compose up event_microservice`.
