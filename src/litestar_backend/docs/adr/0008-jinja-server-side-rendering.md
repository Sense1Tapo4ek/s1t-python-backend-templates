# 0008 — Jinja2 for server-side HTML, single `static/` root for assets
Status: accepted
Date: 2026-05-13

## Context
Three admin pages (`/admin/`, `/admin/login`, `/admin/metrics/{,slug}`) were
rendered with hand-rolled f-string SSR + manual `html.escape` calls. Each
context owned its own `adapters/driving/static/` folder, mounted at a
distinct URL prefix. The pattern was readable for one page, but had grown
to three with overlapping markup (topbar, statusbar, font preconnects) and
two parallel static mounts. Auto-escaping was per-variable, easy to miss.

## Decision
Render HTML with **Litestar's `Template` response + `JinjaTemplateEngine`**
(`litestar[jinja]`). All browser-served assets live in a single
**`static/`** folder at the project root, mirroring the bounded-context
tree (`static/admin/`, `static/admin/log/`, `static/admin/metrics/`,
`static/shared/`). One Litestar mount `/static/...` serves the tree;
the same directory is `TemplateConfig.directory`, so template names
resolve as `<context>/<file>.html`.

## Consequences
- + Auto-escaping by default; one less footgun per variable.
- + Shared layout in `static/shared/_base.html`; pages override blocks.
- + Single static mount, single template engine — no per-context wiring.
- + Asset path == URL path; mental model is one-to-one.
- − Adds `jinja2` (+`markupsafe`) to runtime deps (~600KB).
- − Designers and Python share a directory; convention rule §1.3 in
  `~/.claude/rules/s-ddd_python/structure.md` keeps it ordered.

## Alternatives considered
- **Mako / fastTemplate** — smaller, but ecosystem and Litestar integration
  favour Jinja; rejected.
- **Move SSR client-side (fetch + JSON)** — would force auth-gating logic
  into JS and degrade first-paint; rejected.
- **Per-context templates folder under `adapters/driving/templates/`** —
  proposed first. User feedback: violates the project's principle that
  browser-served assets are wire-level UI, parallel to `docs/` and
  `tests/`, not S-DDD layers. Captured as rule §1.3.
