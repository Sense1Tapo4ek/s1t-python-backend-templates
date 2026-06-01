# 0011 - db_example_sddd: two connection-scope variants (pool vs per-request)
Status: accepted
Date: 2026-06-01

## Context
The db_example_sddd context teaches aiosqlite wiring under Dishka. Two common
patterns exist: a pre-opened pool (APP-scope) and a fresh connection per
request (REQUEST-scope). Neither is universally better; the tradeoffs are
non-obvious and worth demonstrating side by side.

## Decision
Ship both variants in the same context under separate URL prefixes
(`/db-example-sddd/pooled/items` and `/db-example-sddd/per-request/items`).
Domain, app layer, and repo implementation are shared. Only the Dishka
provider and connection source differ.

## Consequences
- + Learners can compare the two DI wiring patterns without switching repos.
- + The shared domain/app/repo code demonstrates that the choice is
    infrastructure-only and does not affect business logic.
- - Two controllers and two facade types add noise for readers who only
    need one pattern; they can ignore the other prefix.

## Alternatives considered
- Single variant (pooled only) - hides the per-request pattern entirely.
- Separate contexts - doubles the boilerplate and obscures that the patterns
  are interchangeable at the boundary.
