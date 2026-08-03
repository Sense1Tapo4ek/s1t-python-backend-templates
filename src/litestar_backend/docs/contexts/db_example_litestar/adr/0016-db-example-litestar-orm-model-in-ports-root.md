---
status: accepted
date: 2026-06-02
---
# 0016 - db_example_litestar: ORM model at the ports/ root

## Context
[ADR 0015](0015-db-example-litestar-orm-model-in-domain.md), which this record
supersedes, placed the ORM model in `domain/` to avoid `driving <-> driven`
imports. But the model is not a domain type -- it carries no business logic; it
is a translation type, the persistence-side analog of the DTO schemas. The
project rule (structure.md §2.2) places a model by *who uses it*. This model is
used by **both** ports branches (driving DTOs/facade serialize it, driven
repos persist it).

## Decision
Move the model to the **`ports/` root** (`ports/orm_models.py`), not under
`driving/` or `driven/` and not in `domain/`. Both branches import it from the
shared `ports/` parent, so there is no `driving <-> driven` crossing.
`ports/driving` still re-exports it for controllers (which may import only
`ports/driving`). The context keeps no `domain/` folder (no business logic).
Supersedes ADR 0015.

## Consequences
- + Model placement matches usage (both branches) and the general rule; no
    `driving <-> driven` model import.
- + No framework-bound type sits in `domain/`; the context simply has no
    `domain/`.
- - `ports/` gains a root-level module (neither driving nor driven) -- a small
    departure from the strict two-subfolder ports split, justified for a
    both-branches translation type.

## Alternatives considered
- `domain/` (ADR 0015) -- treats an ORM row as a domain entity; rejected, no
  business logic lives on it.
- `ports/driven/` -- only correct if the model never surfaced to driving; here
  the DTOs need it, so it would reintroduce a `driving -> driven` import.
