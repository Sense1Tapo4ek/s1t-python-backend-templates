# orders context (realtime_litestar)

For contributors learning event-driven wiring inside a single process: one
domain action (`POST /orders`) raises one domain event that fans out through
Litestar's in-process event bus (`litestar.events`) to two listeners, one of
which re-publishes to `litestar.channels` (Redis stream backend) for a live
SSE feed.

This is an **example context** shipped in the template, alongside
`db_example_sddd`, `db_example_litestar`, and `metrics`. It is Phase 1 of a
three-context event-driven showcase; Phases 2-3 (`jobs_saq`,
`streaming_faststream`) add at-least-once transports. Delete the examples once
you have real contexts.

## Mental model

```
  POST /orders ──> OrderController ──> OrdersFacade.place ──> PlaceOrderUC
                                                                  |
                                                   save() in UoW (asyncpg tx)
                                                                  |
                                                   commit, THEN publish
                                                                  |
                                              IEventBus (LitestarEventBus)
                                                   app.emit("order_placed", ...)
                                                                  |
                       ┌──────────────────────────────┴───────────────────────┐
                 audit_order_placed                              feed_order_placed
              (Counter + structlog)                       channels.publish("orders", ...)
                                                                          |
                                                   RedisChannelsStreamBackend (history=0)
                                                                          |
                                              GET /orders/feed (SSE) -> subscribers
```

In-process bus = `SimpleEventEmitter`: synchronous-ish fan-out within ONE
process, **at-most-once**, **process-local**. Channels adds cross-process
fan-out over Redis. Neither persists: a listener crash or a subscriber that
isn't connected loses the event. That trade-off is the lesson — Phase 3 adds a
broker with delivery guarantees.

## Public surface

### Routes

| Method | Path | Body | Response | Status |
|---|---|---|---|---|
| POST | `/orders` | `PlaceOrderRequest` | `OrderReadDTO` (`OrderModel`) | 201 |
| GET | `/orders` | — (`limit` query, 1-200, default 50) | `list[OrderModel]` | 200 |
| GET | `/orders/feed` | — | `text/event-stream` (SSE) | 200 |

`GET /orders` returns the most recent orders, newest first. `GET /orders/feed`
streams `order_placed` payloads live as Server-Sent Events.

### Domain event

`OrderPlacedEvent(order_id, total, placed_at)` — recorded by `Order.place`,
drained by `PlaceOrderUC` after commit, mapped by `LitestarEventBus` to
`app.emit("order_placed", order_id=str, amount=str, currency=str,
placed_at=isoformat)`. The wire/listener contract is primitives only.

### Wire shapes

- `PlaceOrderRequest` (`msgspec.Struct`): `customer_ref`, `currency` (3 chars),
  `lines: list[OrderLineModel]`. Litestar decodes + validates it at the
  boundary; the facade takes it directly (no `to_command` indirection).
- `OrderModel` (`msgspec.Struct`, read shape): server-assigned `id`, `total`
  (server-computed sum of line subtotals), `status`, `placed_at`.
  `OrderReadDTO = MsgspecDTO[OrderModel]` is the controller `return_dto`.
- `OrderLineModel`: `product_ref`, `quantity` (>=1), `unit_price` (Decimal).

### SSE payload

`{order_id, amount, currency, placed_at}` — all strings. `amount` is the
order total as a decimal string.

### Config (`ORDERS_` prefix)

| Env var | Default | Notes |
|---|---|---|
| `ORDERS_SCHEMA_NAME` | `orders` | Postgres schema this context owns (search_path) |
| `ORDERS_POOL_SIZE` | `4` | asyncpg pool `max_size` (1-32) |
| `ORDERS_RECENT_LIMIT` | `50` | Default recent-list size (1-500) |

Postgres connection settings (`POSTGRES_*`) live in shared `PostgresConfig`
([docs/infra/postgres.md](../infra/postgres.md)). Redis settings (`REDIS_*`)
live in shared `RedisConfig` ([docs/infra/redis.md](../infra/redis.md)).

### Errors

- `EmptyOrder(DomainError)` -> 409. Raised by `Order.place` on zero lines.
  `PlaceOrderRequest.lines` carries **no** boundary `min_length`, so an empty
  order reaches the domain rather than failing as a 400 schema reject — the
  point is to demonstrate the domain rule, not the validator.
- `NegativeMoney`, `CurrencyMismatch` (`DomainError`) -> 409. Enforced by the
  `Money` VO.

## Layers

Full S-DDD context: `domain/` (Order aggregate, OrderLine entity, Money +
OrderStatus VOs, OrderPlacedEvent, errors), `app/` (PlaceOrderUC,
ListRecentOrdersQuery, `IOrderRepo`/`IUoW`/`IEventBus` Protocols), `ports/`
(OrdersFacade + DTOs driving; SqlOrderRepo + SqlUoW + LitestarEventBus driven),
`adapters/` (OrderController + OrderFeedController driving; pg_pool, migrations,
listeners driven; lifespan manager).

`LitestarEventBus` declares a local `_Emitter` Protocol (`emit(event, **kwargs)`)
so the app/ports layers stay framework-free; the provider injects the Litestar
app via `cast(_Emitter, app)` — composition absorbs the framework coupling.

## Migrations

yoyo over the `postgresql+psycopg` backend (psycopg3), applied at lifespan
start via `apply_migrations(yoyo_url)` in `asyncio.to_thread`. Files in
`migrations/orders/` (parallel to `src/`). `001-create-orders.sql` creates the
`orders` schema, `orders.orders`, and `orders.order_lines` (FK cascade), plus
indexes. Migration table `_yoyo_migration` is shared with other contexts; ids
are filename-derived so they don't collide.

## Invariants and gotchas

- **Publish AFTER commit.** `PlaceOrderUC` saves inside the UoW transaction,
  then publishes drained events. A UoW failure raises before publish, so no
  event escapes for a rolled-back order. Combined with the in-process bus this
  is at-most-once: a crash between commit and emit loses the event. No outbox
  in Phase 1 (deferred to Phase 3).
- **Distinct pool DI key.** `db_example_sddd` also provides a bare
  `asyncpg.Pool` at APP scope. Two providers for the same type collide in one
  Dishka container (last registered wins) and would cross-wire db_example's
  pooled repo to the `orders` schema. The orders provider wraps its pool in a
  frozen `OrdersPool` dataclass to give it a unique key. Any future
  asyncpg-pool context must do the same.
- **Channels owns its Redis client.** `build_app` constructs the
  `ChannelsPlugin` with its own `RedisChannelsStreamBackend(history=0, ...)`;
  the plugin starts/stops that client via the app lifecycle, so it needs no
  manual close. `history=0` => the live feed replays no backlog.
- **Schema isolation by search_path**, same as `db_example_sddd`; same shared
  Postgres database. asyncpg autocommits per statement — multi-statement work
  goes through `SqlUoW` (`conn.transaction()`).
- **The two listeners are independent.** `audit_order_placed` increments the
  `orders_placed_total` Prometheus counter and logs; `feed_order_placed`
  re-publishes to the `orders` channel. Either can fail without affecting the
  HTTP response (the emit already returned).

## Pointers

- `src/orders/` — full context source
- `migrations/orders/` — yoyo SQL migration files
- [docs/adr/0020-realtime-litestar-event-bus-channels.md](../adr/0020-realtime-litestar-event-bus-channels.md) — why the in-process bus + Channels
- [docs/infra/redis.md](../infra/redis.md) — Redis as shared infra
- [docs/architecture.md](../architecture.md) — S-DDD layers, DI scopes, lifespan contract
