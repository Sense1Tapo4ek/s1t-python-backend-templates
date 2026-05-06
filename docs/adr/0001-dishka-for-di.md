# 0001 — Dishka for dependency injection
Status: accepted
Date: 2026-05-06

## Context
The template needs an async-friendly DI container with explicit scopes
(APP / REQUEST), no globals, and clean test override hooks. It must
integrate with Litestar's request lifecycle without forcing every handler
to thread dependencies manually.

## Decision
Use Dishka. One `Provider` per bounded context, registered in
`src/root/composition/container.py::build_container`. Default scope is
`APP`; per-request resources (sessions, UoW) get `Scope.REQUEST`.

## Consequences
- + Lazy resolution — graph builds on first request, not at import.
- + One-line concrete-to-interface mapping in providers; tests override by
  swapping providers.
- + Explicit `Scope.APP` vs `Scope.REQUEST` separation maps cleanly to ASGI.
- − Smaller community than FastAPI `Depends`; fewer SO answers.
- − APP-scope laziness requires explicit warm-up in tests that use env
  isolation fixtures.

## Alternatives considered
- punq / dependency-injector — synchronous-first; awkward with async deps.
- Manual constructor wiring — fine until the graph hits ~20 nodes; then it
  becomes the bottleneck for adding contexts.
- FastAPI-style `Depends` — couples DI to the request handler, no clean
  way to share an APP-scope graph with workers and CLI.
