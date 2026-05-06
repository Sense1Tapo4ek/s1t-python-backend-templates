# Dishka

Version: per `pyproject.toml`. Async DI container. Documentation:
<https://dishka.readthedocs.io/>.

For the *why*, see [adr/0001-dishka-for-di.md](../adr/0001-dishka-for-di.md).

## Where it's used

Every context exposes one `Provider` (and optional `*PortBindings`
companion). The root container assembles them in
`src/root/composition/container.py::build_container`:

```python
return make_async_container(
    SharedProvider(channels_plugin=channels_plugin),
    AdminProvider(),
    AdminLogProvider(),
    AdminLogPortBindings(),
    AuthProvider(),
    AuthPortBindings(),
)
```

Litestar integration: `setup_dishka(container=container, app=app)` in
the lifespan handler. After this, `FromDishka[Dep]` + `@inject` works in
controllers.

## Scopes

- `Scope.APP` — process-wide singletons. Default for everything in this
  project. Resolved lazily on first request.
- `Scope.REQUEST` — per-request resources (DB session, UoW). Created
  automatically by the Litestar integration; available in handlers via
  `FromDishka[...]`.

The reader pool is APP-scope because it owns its own lifecycle (open at
startup, close at shutdown). A per-request session would defeat pool
reuse.

## Provider patterns

```python
# admin/log/provider.py
class AdminLogProvider(Provider):
    scope = Scope.APP

    config = provide(AdminLogConfig)
    engine = provide(build_engine)
    repo   = provide(SqliteLogRepo, provides=ILogReader)
    sink   = provide(LogSinkWorker)
```

Rules:
- Map concretes to interfaces with `provides=`. The provider is the only
  place that knows the binding.
- `*PortBindings` companion exists only to keep the main provider focused
  on infra wiring.
- Never import another context's `provider.py` — the root container is
  the only assembly point.

## Container access from adapters

| Caller | Pattern |
|:---|:---|
| Controller | `FromDishka[Dep]` + `@inject` decorator |
| Middleware (APP-scope dep) | `await container.get(Dep)` via `connection.app.state.container` — but **stash it once at lifespan**, don't resolve per request |
| Middleware (REQUEST-scope dep) | `connection.scope["state"]["dishka_container"].get(Dep)` |
| Lifespan / startup | `await container.get(Dep)` via app instance |
| Worker / CLI | `async with container() as request_container: …` |

The middleware optimisation matters because ASGI middleware runs outside
the Dishka request scope. We resolve `AuthFacade` once at lifespan start
into `app.state.auth_facade` rather than walking the container per
request.

## Invariants & gotchas

- **APP-scope graph is lazy.** The first HTTP request triggers
  resolution. Tests that use env-isolation autouse fixtures must warm
  DI eagerly before the fixture wipes env vars. See
  `tests/e2e/conftest.py::e2e_client`.
- **`channels_plugin` is threaded in, not constructed inside.** The
  same instance must reach `Litestar(plugins=[...])` and
  `SharedProvider(channels_plugin=...)`. Constructed in `create_app`
  and passed both ways. See [subsystems/event_bus.md](../subsystems/event_bus.md).
- **Container close is idempotent in lifespan.** The shutdown path
  always reaches `await container.close()` regardless of partial
  start failures.

## Pointers

- ADR: [0001-dishka-for-di.md](../adr/0001-dishka-for-di.md)
- Code: `src/root/composition/container.py`, `src/*/provider.py`
- Litestar integration: <https://dishka.readthedocs.io/en/stable/integrations/litestar.html>
