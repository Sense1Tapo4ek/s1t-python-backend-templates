# Error hierarchy

Semantic exceptions per layer, caught at adapter boundaries by the global
exception handlers. Defined in `src/shared/generics/errors.py`.

```
Exception
└── LayerError
    ├── DomainError      -> 409 Conflict       (WARNING)
    ├── AppError         -> 422 Unprocessable  (WARNING)
    └── PortError        -> 503 Unavailable    (ERROR + traceback)
```

The discipline in one line: raise semantic errors named after the violated
invariant, wrap raw infrastructure exceptions at driven ports, log only at
the adapter boundary that maps the error to a response. This page documents
the project-specific wiring; the raise/catch table below is the contract.

**Deliberate divergence from the canonical S-DDD ruleset.** The reusable
ruleset lists a fifth class, `AdapterError` (-> 500), for framework/I/O
failures raised in `adapters/`. This template omits it: no honest raise-site
exists here (driven adapters wrap infra failures as `PortError` at the port
boundary), and a mapped-but-never-raised class is a dead duplicate of the PROD
catch-all `Exception -> 500` (`unexpected_to_problem`). A truly unexpected
adapter failure still renders as a generic problem+json 500 via that catch-all.
Add `AdapterError` back only when a real adapter raise-site appears.

## Raise / catch contract

| Layer | Raises | Catches | Wraps |
|:---|:---|:---|:---|
| Domain | `DomainError` | nothing | nothing |
| App | `AppError` | `DomainError` (only to change context) | rare |
| Ports/driven | `PortError` | infra exceptions (asyncpg, httpx) | infra -> `PortError` |
| Adapters/driving | -- | all `LayerError` subtypes | error -> HTTP response |

Domain and app errors propagate **unchanged** through ports up to adapters.
Driven ports are the wrap point for raw infrastructure exceptions.

## Global handler registration

Every error is rendered as RFC 9457 `application/problem+json` (ADR 0018).
Wired in `src/root/composition/app.py::build_app`, in two parts.

Framework `HTTPException`s (validation, 404 routing, 405) are rendered by the
plugin:

```python
ProblemDetailsPlugin(
    ProblemDetailsConfig(
        enable_for_all_http_exceptions=True,
        exception_handler=problem_handler,
    )
)
```

`LayerError` subtypes are converted by the pure functions in
`shared/adapters/problem_details.py`, registered as **app-level** handlers
(`_build_exception_handlers`), each wrapped via `_as_handler` ->
`problem_handler` (which sets the RFC 9457 `instance` from the request path):

```python
EXCEPTION_TO_PROBLEM = {
    DomainError:          domain_to_problem,       # 409
    AppError:             app_to_problem,          # 422
    JwtDisabledError:     jwt_disabled_to_problem, # 503
    NotFoundError:        not_found_to_problem,    # 404 (MRO: wins over AppError)
    AlchemyNotFoundError: not_found_to_problem,    # 404
    PortError:            port_to_problem,         # 503
}
```

App-level (not the plugin's exception map) because Litestar 2.23's plugin
bypasses `config.exception_handler` for mapped types, dropping `instance`.
Two retained admin handlers sit alongside:
`NotAuthorizedException -> not_authorized_handler` (401) and
`PermissionDeniedException -> permission_denied_handler` (403). They return a
problem+json body for API callers, but under `/admin/*` with an HTML `Accept`
they render a 303 login redirect / a forbidden HTML page instead.

## Custom error pattern

Classic `__init__` + `super().__init__(msg)`. Never `@dataclass` for
exceptions. Name reflects the violated invariant, not the technical cause.

```python
class OrderAlreadyPaid(DomainError):
    def __init__(self, order_id: UUID):
        self.order_id = order_id
        super().__init__(f"Order {order_id} is already paid")
```

## DEV vs PROD

- **DEV** (`APP_ENV=dev`): `Litestar(debug=True)` renders full tracebacks
  on 500. The catch-all `Exception -> unexpected_to_problem` is **not**
  registered -- Litestar's debug renderer wins.
- **PROD**: `debug=False`; `unexpected_to_problem` returns a problem+json
  500 with a generic `detail`. Tracebacks never reach the client; full
  context goes to the `root.errors` logger.

## snitchbot interaction

`install_snitchbot(app)` registers an `Exception` handler for crash
reporting that would otherwise render framework `HTTPException`s as a bare
500. Because the problem-details plugin runs with
`enable_for_all_http_exceptions=True`, those `HTTPException`s are rendered
as problem+json ahead of snitchbot's bare-500 path. There is no longer a
hand-written `HTTPException` catch-all.

## Pointers

- Code: `src/shared/generics/errors.py` (hierarchy),
  `src/shared/adapters/problem_details.py` (converters + `problem_handler`),
  `src/root/composition/app.py` (wiring),
  `src/shared/adapters/openapi.py` (`ProblemDetail` schema),
  `src/admin/adapters/driving/error_handlers.py` (401/403 SSR handlers).
- Wire contract: [../../../../docs/contract/errors.md](../../../../docs/contract/errors.md).
- ADR: [../adr/0018-rfc9457-problem-details.md](../adr/0018-rfc9457-problem-details.md).
