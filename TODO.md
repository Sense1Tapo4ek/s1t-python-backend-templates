# TODO

Deferred work with rationale. Land each one as its own PR.

## Litestar idiom: Template engine for HTML responses

**Scope:** Replace the hand-rolled f-string SSR in
`src/admin/metrics/adapters/driving/api/metrics_overview_controller.py`
(and `src/admin/adapters/driving/api/admin_controller.py`,
`login_controller.py`) with Litestar's `Template` response + a template
engine plugin (Jinja2 or Mako).

**Why deferred:** the current f-string approach is intentional and
lightweight — adding a template engine introduces a runtime dep, a
plugin registration, and per-template files. Worth doing if/when:
- A third+ HTML controller needs the same layout (DRY pressure).
- Designers want to edit templates without touching Python.
- Auto-escaping becomes a security concern (currently we hand-call
  `html.escape` on every variable).

**Approx effort:** half a day (engine wiring + template files + tests).

## Litestar idiom: ServerSentEvent for SSE log tail

**Scope:** Replace the manual `Stream(...) + f"data: ...\n\n"` framing
in `src/admin/log/adapters/driving/api/logs_controller.py::api_stream`
with Litestar 2.21's `ServerSentEvent` response class.

**Why deferred:** the swap is ~4 lines smaller but needs verification
that `ServerSentEvent` either preserves or correctly applies our
`_SSE_HEADERS` dict (`Cache-Control: no-cache`, `X-Accel-Buffering:
no`). Without those headers nginx and some browsers buffer the
response, defeating the live-tail UX. Needs manual smoke against the
real `/admin/logs/` UI + an nginx-in-front scenario before merging.

**Approx effort:** half a day (swap + manual smoke + integration test
that asserts headers on the response).

## Compose: wire the `seed` profile

**Scope:** `scripts/seed_logs.py` exists and works locally, but
`docker-compose.yml` doesn't yet expose it as a service. Once the
pending log-subsystem updates to `docker-compose.yml` land (valkey +
log-sink services), append the snippet below under `services:`:

```yaml
seed:
  profiles: ["demo"]
  image: litestar-base:local
  env_file:
    - .env
  environment:
    VOLUME_PATH: /data
  volumes:
    - app_data:/data
    - ./scripts:/app/scripts:ro
    - ./tests:/app/tests:ro
  depends_on:
    app:
      condition: service_started
  entrypoint: ["/usr/bin/tini", "--"]
  command:
    - "python"
    - "/app/scripts/seed_logs.py"
    - "--count"
    - "${SEED_COUNT:-1000}"
    - "--minutes"
    - "${SEED_MINUTES:-120}"
```

Usage: `docker compose --profile demo up seed` after the stack is up.
The service is one-shot — it writes N rows directly to the SQLite
volume (bypassing Valkey/sink) and exits. Re-run any time with
`SEED_COUNT=...` to refresh.

**Why deferred:** keeping `docker-compose.yml` out of the metrics
branch — it carries pre-existing log-subsystem modifications that
should land separately.

## Notes

The Template-engine and ServerSentEvent items were intentionally
skipped from the conciseness audit in commit 1430fdd. Everything else
from that audit either landed in 1430fdd / 151adee or was deemed not
worth the trade-off (see commit messages).
