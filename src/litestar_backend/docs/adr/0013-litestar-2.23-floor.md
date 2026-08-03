---
status: accepted
date: 2026-06-01
---
# 0013 - Litestar minimum version raised to 2.23.0

## Context
advanced-alchemy 1.11's Litestar extension uses `litestar.di.NamedDependency`,
which was introduced in Litestar 2.22/2.23. The previous floor was 2.21.x.

## Decision
Raise `pyproject.toml` lower bound to `litestar[jinja,prometheus]>=2.23.0`.

## Consequences
- + Unblocks advanced-alchemy 1.11 integration without import-time errors.
- - Projects forked before this bump that pin Litestar < 2.23 cannot use
    db_example_litestar without upgrading Litestar.

## Alternatives considered
- Vendor a compatibility shim for NamedDependency - unnecessarily complex;
  the Litestar 2.23 release is stable and non-breaking for this project.
