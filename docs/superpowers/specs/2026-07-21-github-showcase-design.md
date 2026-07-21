# GitHub Showcase: README + Pages Landing

Date: 2026-07-21. Status: approved (brainstormed with visual companion,
style validated against sense1tapo4ek.com dark theme).

## Goal

Make the repo a shelf-ready showcase for the community (Python devs looking
for a Litestar/DDD production starter): a rewritten English README, a
hand-crafted GitHub Pages landing, and repo dressing. Architecture, patterns,
and service interaction lead; features appear only as proof of patterns.

## 1. Landing — `site/index.html`

One self-contained HTML file: inline CSS/JS, no build step, no frameworks,
no analytics. Fonts via Google Fonts (Literata, Golos Text, JetBrains Mono)
with system fallbacks. Dark theme only.

Design tokens (from sense1tapo4ek.com `[data-theme=dark]`, brightened per
approved hero v2):

| Token | Value |
|:--|:--|
| paper / raised / sunken | `#211c16` / `#2a241d`..`#322b21` grad / `#1a1611` |
| ink / soft | `#f7f0e0` (headings `#f4ecdc`) / `#c9bda8` |
| faint / line / line-strong | `#796e5e` / `#3a3228` / `#4c4234`..`#6a5c44` |
| accent (brass) | `#e3b661`, CTA glow `rgba(227,182,97,.35)` |
| moss / clay | `#9cc48c` / `#d98f70` |
| type | Literata (serif, headings), Golos Text (body), JetBrains Mono (code/overlines) |
| signature | geo glyphs `▵ ▢ ◇` colored ochre/moss/clay; grain overlay; wordmark `s1t-litestar-template.` with brass dot |

Sections, in order (approved skeleton v2):

1. **Hero** — overline `▵ production-shaped python monorepo`; H1 "An
   architecture you can *read*." (brass on "read"); subline: two services,
   zero shared code, strict DDD; CTAs: `Use this template` (brass, glow) +
   `Read the architecture ->`; warm radial glow behind.
2. **Topology** — two service cards joined by `video_uploaded ──▶` /
   `◀── video_status` mono arrows; caption "only wire contracts cross the
   boundary — not a single shared import".
3. **S-DDD layers** — `adapters -> ports -> app -> domain`, imports point
   inward, enforced by import-linter. Interactive: hovering a layer
   highlights its files in a context tree render.
4. **Pattern catalog (center of gravity)** — 6 cards: transactional outbox,
   inbox dedup, composite auth chain, keyset pagination, event envelope,
   graceful drain. Each: mini ASCII diagram + 2 lines of "why" + links to
   code path and ADR on GitHub.
5. **End-to-end scenario** — the video pipeline
   (`POST /videos -> outbox tx -> relay -> stream -> 3 SAQ jobs -> join ->
   video_status -> state machine -> SSE`); ONE animated spark traverses the
   path (the page's only motion); steps labeled with §4 pattern names.
6. **Quick start + docs map** — `cp .env.example .env && docker compose up
   --build`; link tiles: architecture.md, contracts, ADR index, per-service
   docs.
7. **Philosophy** — closing serif line: "A template, not a framework: fork
   it, rename it, delete what you don't need."
8. **Footer** — colored glyphs, "drafted in ink", "part of the s1t template
   family", GitHub link.

Responsive; wide diagrams scroll inside their own container. All links point
at the GitHub repo (no second copy of docs content — the landing owns no
facts, mirroring the feature-map discipline).

## 2. Pages deploy — `.github/workflows/pages.yml`

First CI workflow in the repo. Trigger: push to `main`, paths `site/**` (+
`workflow_dispatch`). Jobs: checkout -> `actions/upload-pages-artifact`
(path `site/`) -> `actions/deploy-pages`. Permissions `pages: write`,
`id-token: write`. Manual one-time step: repo Settings -> Pages -> source
"GitHub Actions".

## 3. README rewrite (English)

Same narrative as the landing, static: hero claim + 3-4 restrained badges
(Python 3.12+, Litestar 2.24+, tests, license) + landing link -> topology
ASCII -> layers -> pattern table (pattern / where / ADR) -> end-to-end
scenario -> quick start -> docs map -> philosophy. Keeps the existing
run-card facts (URLs table, SAQ panel, test commands) but demotes them below
the architecture story. Budget <= 200 lines (documentation.md §4). Existing
doc links must survive (linkcheck clean).

## 4. Repo dressing

- `gh api`: description ("Production-shaped Litestar monorepo template:
  strict DDD, transactional outbox, event-driven two-service topology") +
  topics: litestar, python, ddd, hexagonal-architecture, template,
  event-driven, transactional-outbox, saq, faststream, valkey.
- Social preview: `site/social-preview.png` 1280x640 generated from an SVG
  in the landing palette (wordmark + topology motif). Uploaded manually in
  Settings (no API for it).

## Out of scope

Light theme, MkDocs/doc-site, JS frameworks, analytics, i18n (page is
English-only), any change to the docs/ corpus content.

## Testing

- Landing: visual pass in browser (desktop + narrow viewport), all links
  resolve to existing repo paths (extend the linkcheck script to site/
  hrefs), HTML validates (no external requests beyond Google Fonts).
- Workflow: green run on first push; page serves at the Pages URL.
- README: linkcheck clean; line budget respected; renders correctly on
  GitHub (tables, ASCII blocks).
