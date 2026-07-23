# Glossary

One-sentence definitions of the S-DDD terms used across this repo. Authoritative
detail lives in [architecture.md](architecture.md); this page is a quick
lookup, not a substitute.

## Layers

- **Domain layer** -- pure business logic; stdlib only, no framework, no outer layer.
- **App layer** -- orchestration of use cases; depends only on the domain and its own `interfaces/` Protocols.
- **Ports** -- the context boundary: `driving/` (inbound: facades, schemas, guards) and `driven/` (outbound: repos, gateways, ACLs).
- **Adapters** -- infrastructure; the only place frameworks (Litestar, SQLAlchemy, redis) are allowed.

## Tactical building blocks

- **Aggregate Root** -- the transactional consistency boundary; all state changes pass through its methods; accumulates domain events.
- **Entity** -- an object with identity and a lifecycle that belongs to an aggregate; never queried independently.
- **Value Object (VO)** -- an immutable, identity-free value defined by its attributes; justified only by an invariant, a method, or >=2 indivisible fields.
- **NewType** -- a zero-cost `typing.NewType` alias used instead of a VO when only same-typed-id disambiguation is needed.
- **Domain Event** -- an immutable, past-tense record of something that happened in the domain; domain types only, never serialized to a broker.
- **Integration Event** -- the wire form of a domain event; primitives + metadata, serialized for a broker; defined in `ports/`.
- **Domain Service** -- stateless computation that does not belong to a single entity (`@staticmethod`/`@classmethod` only).
- **Policy / Specification** -- an isolated business rule / a predicate, expressed as stateless domain logic.

## Application building blocks

- **Use Case** -- an atomic state-changing action; a frozen dataclass with a single `__call__`.
- **Query** -- a read-only action; like a use case but no UoW, no save, no event collection.
- **Command** -- an immutable input object for a use case with 3+ arguments.
- **Workflow / Saga** -- coordination of multiple use cases with compensation on partial failure; decides what to call when, holds no domain logic.
- **Interface** -- a `Protocol` declared in `app/interfaces/`; carries the full contract docstring; implemented in `ports/driven/`.

## Boundary building blocks

- **Facade (driving port)** -- a context's public API, split by actor; thin (schema -> command -> use case).
- **Repository (driven port)** -- persistence access implementing an `app/interfaces/` Protocol; maps domain <-> ORM model.
- **Gateway (driven port)** -- an outbound client to an external system.
- **ACL (Anti-Corruption Layer)** -- the only module allowed to import another context's `ports/driving/`; translates between domains.
- **Unit of Work (UoW)** -- the transaction boundary; an async context manager that commits on clean exit and rolls back on error.

## Messaging building blocks

- **Outbox** -- a table written in the same transaction as the state change; drained asynchronously to guarantee at-least-once publish.
- **Relay** -- the background task that drains the outbox to a broker and marks rows sent (uses `SELECT ... FOR UPDATE SKIP LOCKED`).
- **Inbox** -- the consumer-side dedup table keyed by `event_id` that makes an at-least-once consumer idempotent.
- **Consumer** -- a driving adapter that reacts to an inbound message and follows the same path as an HTTP request (adapter -> facade -> use case).

## Composition & errors

- **Provider** -- a Dishka `Provider`; the only place that maps a concrete implementation to its interface.
- **Container** -- the assembled Dishka graph; built once at startup in `root/composition/`.
- **Lifespan Manager** -- app-lifecycle start/stop glue (pools, migrations, background tasks) registered in the lifespan.
- **LayerError hierarchy** -- `DomainError` (409) / `AppError` (404/422) / `PortError` (503); raised inward, caught and rendered as `problem+json` at the adapter boundary. A truly unexpected failure renders a generic 500 via the PROD catch-all. (The canonical ruleset's `AdapterError` is deliberately omitted -- no honest raise-site; see the error-hierarchy subsystem doc.)
