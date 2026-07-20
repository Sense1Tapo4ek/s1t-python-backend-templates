# FastStream (Valkey Streams consumer)

Version: faststream[redis,cli] (CLI extra required -- the runtime CMD is
`faststream run root.entrypoints.consumer:app`).

Subscribes to the `video_uploaded` stream via a consumer group
(`StreamSub(VIDEO_UPLOADED_STREAM, group="media_processing", consumer=_CONSUMER)`),
acks each message after handling.

## DI / facade injection

The facade is NOT a global. It is resolved from the Dishka container in the
`app.on_startup` hook and stored in FastStream's application context:

```python
app.context.set_global("facade", facade)
```

The subscriber retrieves it via FastStream's native `Context` mechanism:

```python
async def on_video_uploaded(
    body: dict[str, str],
    msg: RedisMessage,
    facade: MediaProcessingFacade = Context("facade"),
) -> None: ...
```

## Consumer identity

A unique per-instance consumer name is derived from hostname:

```python
_CONSUMER = f"{CONSUMER_GROUP}-{socket.gethostname()}"
```

This ensures multiple replicas of the consumer service each own their
pending-entry list and do not steal each other's messages.

## Error handling

- **Malformed payload** (`msgspec.MsgspecError`): logged at WARNING and
  ACKed immediately. The entry is never redelivered (poison-pill drop).
- **Transient failures** (`PortError` or other exceptions): propagate
  without ACK, leaving the entry in the pending-entries list for
  redelivery by SAQ's retry mechanism.
- In both cases `msg.ack()` is called **after** the handler returns,
  ensuring the happy-path entry is also ACKed exactly once.

## Metrics server

A Prometheus HTTP server runs on port 9100 inside the container
(`start_http_server(cfg.metrics_port)`). Docker Compose maps this to
host port **9101** for the consumer service.

Run: `docker compose up event_microservice`.
