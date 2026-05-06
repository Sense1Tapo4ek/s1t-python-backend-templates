# Error hierarchy

Semantic exceptions per layer, caught at adapter boundaries by the global
exception handlers. Defined in `src/shared/generics/errors.py`.

```
Exception
└── LayerError
    ├── DomainError      → 409 Conflict       (WARNING)
    ├── AppError         → 422 Unprocessable  (WARNING)
    ├── PortError        → 503 Unavailable    (ERROR + traceback)
    └── AdapterError     → 500 Internal       (EXCEPTION)
```

The full discipline (when to wrap, when to pass through, what to log) lives
in `~/.claude/rules/s-ddd_python/errors.md`. This page documents the
project-specific wiring.

## Raise / catch contract

| Layer | Raises | Catches | Wraps |
|:---|:---|:---|:---|
| Domain | `DomainError` | nothing | nothing |
| App | `AppError` | `DomainError` (only to change context) | rare |
| Ports/driven | `PortError` | infra exceptions (aiosqlite, httpx) | infra → `PortError` |
| Adapters/driving | — | all `LayerError` subtypes | error → HTTP response |

Domain and app errors propagate **unchanged** through ports up to adapters.
Driven ports are the wrap point for raw infrastructure exceptions.

## Global handler registration

Wired in `src/root/entrypoints/api.py::create_app`:

```python
exception_handlers = {
    DslSyntaxError:               dsl_syntax_handler,
    InvalidLogFilterError:        invalid_log_filter_handler,
    NotAuthorizedException:       not_authorized_handler,
    PermissionDeniedException:    permission_denied_handler,
    ValidationException:          validation_exception_handler,
    HTTPException:                _http_exception_handler,
    DomainError:                  domain_error_handler,
    AppError:                     app_error_handler,
    PortError:                    port_error_handler,
    AdapterError:                 adapter_error_handler,
}
if not is_dev:
    exception_handlers[Exception] = fallback_500_handler
```

Order matters. Litestar resolves the most specific handler, but
specialised types must be registered before their bases.

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
  on 500. The catch-all `Exception → fallback_500_handler` is **not**
  registered — Litestar's debug renderer wins.
- **PROD**: `debug=False`; `fallback_500_handler` returns an opaque
  `{"detail": "internal server error"}`. Tracebacks never reach the
  client.

## snitchbot workaround

`snitchbot.install(app)` registers an `Exception` handler that re-raises
`HTTPException`, which Litestar then renders as a bare 500 with an empty
body. `_http_exception_handler` is the catch-all that restores the
original `status_code` and `detail`. Remove if/when snitchbot moves
crash reporting into middleware.

## Pointers

- Code: `src/shared/generics/errors.py`,
  `src/shared/adapters/error_handlers.py`,
  `src/admin/log/adapters/driving/error_handlers.py`,
  `src/admin/adapters/driving/error_handlers.py`.
- Discipline: `~/.claude/rules/s-ddd_python/errors.md`.
