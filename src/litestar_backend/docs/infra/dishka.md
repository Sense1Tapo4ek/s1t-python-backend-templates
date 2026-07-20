# Dishka

Version: per `pyproject.toml`. Async DI container. Documentation:
<https://dishka.readthedocs.io/>.

For the *why*, see [adr/0001-dishka-for-di.md](../../../../docs/adr/0001-dishka-for-di.md).

## Where it's used

Every context exposes one `Provider`. The root container assembles them
in `src/root/composition/container.py::build_container`:

```python
return make_async_container(
    SharedProvider(),
    AdminProvider(),
    AdminLogWebProvider(),
    AuthProvider(),
    DbExampleLitestarProvider(),
    MediaInfraProvider(),
    MediaWebProvider(),
    context={ChannelsPlugin: channels},
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

A DB engine and the Valkey client are APP-scope because they own their
lifecycle (open at startup, closed on container teardown). The per-request
DB session (`Scope.REQUEST`) layers on top so pool reuse is preserved.

## Provider patterns

```python
# admin/log/provider.py
class AdminLogWebProvider(Provider):
    scope = Scope.APP

    config = provide(AdminLogConfig)
    source = provide(LogFileSource)
    reader = provide(FileLogReader, provides=ILogReader)
    follower = provide(FileLogReader, provides=ILogFollower)
    facade = provide(LogsFacade)
```

Rules:
- Map concretes to interfaces with `provides=`. The provider is the only
  place that knows the binding.
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
- **`build_container` threads the `ChannelsPlugin`.** It takes
  `channels: ChannelsPlugin` and registers it as Dishka context
  (`context={ChannelsPlugin: channels}`) so the media feed publisher can
  inject it. `SharedProvider` provides the cross-cutting singletons
  (configs, clock, Valkey client, readiness probe).
- **Container close is idempotent in lifespan.** The shutdown path
  always reaches `await container.close()` regardless of partial
  start failures.

## Pointers

- ADR: [0001-dishka-for-di.md](../../../../docs/adr/0001-dishka-for-di.md)
- Code: `src/root/composition/container.py`, `src/*/provider.py`
- Litestar integration: <https://dishka.readthedocs.io/en/stable/integrations/litestar.html>
