# Jinja2 (HTML templating)

Version: `jinja2` 3.1+ bundled via `litestar[jinja]`. Documentation:
<https://jinja.palletsprojects.com/>.

For the *why*, see [adr/0008-jinja-server-side-rendering.md](../adr/0008-jinja-server-side-rendering.md).

## Where it's used

`src/root/composition/app.py::build_app` (the entrypoint `create_app` is a
thin re-export) wires one engine:

```python
template_config=TemplateConfig(
    directory=PROJECT_ROOT / "static",
    engine=JinjaTemplateEngine,
)
```

Controllers return `litestar.response.Template(template_name=..., context=...)`.
Currently four places:

- `admin/adapters/driving/api/admin_controller.py` -> `admin/dashboard.html`
- `admin/adapters/driving/api/login_controller.py` -> `admin/login.html`
- `admin/log/adapters/driving/api/logs_controller.py` -> `admin/log/index.html`
- `admin/adapters/driving/error_handlers.py` -> `admin/forbidden.html` (403)

## Layout

All templates and browser assets live under one project-root `static/`
folder, mirroring the context tree. The convention: one static root for the
whole service (no per-context `adapters/driving/static/` folders); a single
Litestar mount `/static/...` and a single `TemplateConfig(directory="static")`;
template names are paths relative to that root (`"admin/log/index.html"`);
`shared/` holds layout used by two or more contexts; file names inside a
sub-folder carry no context prefix (the folder already encodes it).

```
static/
  shared/_base.html          # scaffold (head, title, blocks)
  admin/dashboard.html
  admin/login.html
  admin/forbidden.html
  admin/log/index.html
  admin/log/{style.css, tail.js}
```

`_base.html` defines four blocks:

| Block | Use |
|:---|:---|
| `title` | `<title>` text |
| `head_extra` | per-page `<link>` / `<meta>` |
| `body` | main content |
| `scripts` | tail `<script>` tags |

Child templates `{% extends "shared/_base.html" %}` and override blocks.

## Invariants

- **Auto-escape is on by default** for `.html` files. Pass raw values via
  `context={...}`; do NOT call `html.escape` in Python. Use `{{ x | safe }}`
  only for pre-rendered HTML fragments.
- **Template name == path under `static/`.** Do not pass absolute paths.
- **Assets URL == file path under `static/`.** `<link href="/static/admin/log/style.css">`
  loads `static/admin/log/style.css`. The single mount `/static/...` in
  `build_app` enforces this.
- **No per-context `adapters/driving/static/` folders.** The convention
  is deprecated; rule §1.3 forbids it.

## Gotchas

- `Template` from exception handlers works (Litestar attaches the engine
  on the response at send time), but the request must reach the handler —
  middleware short-circuits before that don't render templates.
- Static-mount cache headers: 1h `max_age` is set in `build_app`. For
  designer iterations, hard-reload the browser or temporarily drop the
  `cache_control=` argument.
- `_base.html` includes a `<link>` to Google Fonts. CSP must allow
  `https://fonts.googleapis.com` and `https://fonts.gstatic.com`; see
  `root/config.py::security_csp`.
