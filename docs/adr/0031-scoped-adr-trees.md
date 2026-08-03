---
status: accepted
date: 2026-07-20
---
# 0031 - Split the single ADR folder into scope-level trees

## Context
All ADRs lived in one root `docs/adr/` while the repo grew into a 2-service
monorepo (ADR 0026). Service- and context-scope decisions sat next to
repo-shape ones, and the root docs tree carried both services' reference
pages, violating the narrowest-tree placement rule.

## Decision
One-time split, files relocated WITHOUT renumbering -- the path becomes the
namespace. Project scope stays in `docs/adr/`; service scope moves to
`src/<svc>/docs/adr/`; the `db_example_litestar` context (4 ADRs, above the
3+ threshold) gets `contexts/db_example_litestar/adr/`. Each tree numbers
independently; cross-tree references are path-qualified. Provenance is an
Origin column in each tree's README. Service reference pages (contexts,
subsystems, service-exclusive infra) move to `src/<svc>/docs/`; platform
substrate (Postgres, Valkey) and all wire contracts stay at root.

## Consequences
- + A page or decision lives in the tree that matches its blast radius.
- + Services stay extractable: their docs travel with `src/<svc>/`.
- − Historical links to `docs/adr/NNNN` and `docs/<svc>/` paths break; fixed
    across the corpus in the same change.

## Alternatives considered
- Keep one flat `docs/adr/` -- mixes blast radii, blocks service extraction.
- Renumber per tree from 0001 -- breaks the "never renumber" audit trail.
