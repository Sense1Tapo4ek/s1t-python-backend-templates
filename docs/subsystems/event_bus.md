# Event bus

Typed, in-process pub/sub for domain events. Built on
[Litestar Channels](https://docs.litestar.dev/2/usage/channels.html).

For the *why*, see [adr/0002-litestar-channels-event-bus.md](../adr/0002-litestar-channels-event-bus.md).

## Mental model

The bus is a thin typed dispatcher over the plugin's raw bytes-on-channels
primitive. Business code only ever sees `IEventBus`.

```
use case ── publish(event) ──▶ ChannelsEventBus
                                      │
                          msgspec.encode (JSON bytes)
                                      ▼
                              ChannelsPlugin (memory)
                                      │
                          fan-out per (event_type, handler) task
                                      ▼
                          msgspec.decode → handler(event)
```

Channel name: `event:{module}.{QualName}`. Stable across restarts, unique
per event class, readable in logs.

## Public surface

| Symbol | Where | Role |
|:---|:---|:---|
| `IEventBus` | `shared/app/i_event_bus.py` | Protocol — public surface for use cases. |
| `ChannelsEventBus` | `shared/adapters/driven/event_bus/` | Implementation. msgspec wire format, per-handler asyncio task. |
| `ChannelsPlugin` | created in `root/entrypoints/api.py::_build_channels_plugin` | Single instance shared by Litestar transport (SSE) and the bus. |

## Wire format

`msgspec.json` — see [adr/0005-msgspec-wire-payloads.md](../adr/0005-msgspec-wire-payloads.md).
Native `UUID`/`Decimal`/`datetime`/frozen-dataclass support; type-driven
decode reconstructs the exact dataclass on the consumer side.

## Define an event

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class OrderPaidEvent:
    order_id: UUID
    amount: Decimal
    currency: str
    paid_at: datetime
```

Rules (per S-DDD `domain.md` §5):
- Past-tense name + `Event` suffix.
- `frozen=True, slots=True, kw_only=True`.
- Stdlib types and domain VOs only — no Pydantic, no DTOs.

## Publish from a use case

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class PayOrderUc:
    _repo: IOrderRepo
    _uow: IUOW
    _bus: IEventBus

    async def __call__(self, order_id: UUID) -> UUID:
        order = await self._repo.get_by_id(order_id)
        order.pay()
        async with self._uow:
            await self._repo.save(order)
        for event in order.collect_events():
            await self._bus.publish(event)
        return order.id
```

`publish()` only enqueues. Delivery to handlers is async. Always
publish AFTER commit — if the transaction fails, no event leaks.

## Subscribe a handler

Handlers register in the lifespan **before** `bus.start()`. The bus
refuses late subscriptions because their tasks would miss in-flight
events.

```python
# root/entrypoints/api.py — inside lifespan()
event_bus = await container.get(IEventBus)
handler = await container.get(SendReceiptOnOrderPaidHandler)
event_bus.subscribe(OrderPaidEvent, handler)
await event_bus.start()
```

Handler shape: `Callable[[E], Awaitable[None]]`. A frozen dataclass with
`__call__` is the canonical form.

## Failure isolation

Each `(event_type, handler)` pair runs in its own task.
- A handler exception is logged with full traceback; the loop continues.
- Sibling handlers for the same event are unaffected.
- The publishing use case is unaffected — `publish()` only enqueues.

Malformed payloads (msgspec `DecodeError`) are logged and skipped, never
fatal. Most likely cause: producer/consumer schema drift.

## Backpressure

Configured on the plugin, not on the bus:
- `subscriber_max_backlog` — per-subscriber queue size.
- `subscriber_backlog_strategy="dropleft"` — when full, oldest message
  drops silently. We use this for the log broadcast channel: a slow SSE
  consumer must never back-pressure the writer.

If your domain can't tolerate dropped events, switch to
`backlog_strategy="backoff"` and size the backlog deliberately.

## What is NOT the event bus

- **Cross-context synchronous calls** — use an ACL in `ports/driven/acl/`.
- **Cross-process events to external brokers** (Kafka, RabbitMQ) — map a
  domain event to a Pydantic *integration event* in `ports/driven/`.
- **Log fan-out** — `ChannelsLogBroadcaster` uses the same plugin but a
  fixed channel `log.broadcast` and raw-string payloads. Don't put
  domain events on `log.broadcast`.

## Switching backends

```python
# root/entrypoints/api.py::_build_channels_plugin
from litestar.channels.backends.redis import RedisChannelsBackend
from redis.asyncio import Redis

return ChannelsPlugin(
    backend=RedisChannelsBackend(redis=Redis.from_url(redis_url)),
    arbitrary_channels_allowed=True,
    subscriber_max_backlog=...,
    subscriber_backlog_strategy="dropleft",
)
```

No business code, `IEventBus` consumers, or domain events change.

## Testing

Tests instantiate the plugin via its async context manager — **not**
through `AsyncTestClient`. The test client runs the lifespan in a
separate portal thread, leaving the plugin's queues stranded on a
different event loop and deadlocking `publish()`.

```python
async with plugin:
    bus = ChannelsEventBus(_channels=plugin)
    bus.subscribe(OrderPaidEvent, handler)
    await bus.start()              # waits until subscriber is live
    await bus.publish(event)
```

`bus.start()` blocks until every worker has entered `start_subscription()`.
Without that, a `publish()` immediately after `start()` would race the
subscriber registration and drop the message.

## Pointers

- ADR: [0002-litestar-channels-event-bus.md](../adr/0002-litestar-channels-event-bus.md)
- Code: `src/shared/app/i_event_bus.py`, `src/shared/adapters/driven/event_bus/`
- Wiring: `src/root/entrypoints/api.py::_build_channels_plugin`, `lifespan`
