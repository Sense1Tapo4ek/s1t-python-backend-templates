# Development workflow

How to work the local inner loop and the commit gate. Audience: contributor.
Docker runs the whole stack (`docker compose up`); the tools below are for fast
local iteration and the pre-commit gate. Layers, DI and invariants live in
[architecture.md](architecture.md).

## One-time setup

The repo is a two-service uv monorepo. Each service (`src/litestar_backend`,
`src/event_microservice`) is its own uv project with its own `.venv`.

```bash
# Per-service venvs (or just let Docker build them)
cd src/litestar_backend  && uv sync
cd ../event_microservice && uv sync

# Task runner — wraps every canonical command
go install github.com/go-task/task/v3/cmd/task@latest   # or: brew install go-task
#   no Go toolchain? -> uv tool install go-task-bin

# Commit gate
uv tool install pre-commit
pre-commit install            # wires .git/hooks/pre-commit
```

`pre-commit install` refuses while `core.hooksPath` is set. The repo's default is
`.git/hooks`, so it is safe to clear: `git config --unset core.hooksPath`.

## The toolchain is unified

Both services pin the SAME dev toolchain in their `pyproject.toml`:

| Tool | Version | Pinned in |
|---|---|---|
| ruff | `==0.15.22` | each service's `[dependency-groups] dev` |
| mypy | `==2.3.0` | each service's `[dependency-groups] dev` |

Keep the two pins identical. To upgrade: bump BOTH, run `task fmt && task check`,
commit together. `task check` and pre-commit run the tools through each service's
own uv venv, so a drift surfaces immediately.

Why exact `==` pins: ruff's formatter output and mypy's checks change between
releases; a floating `>=` would reformat files or report types differently on each
machine and in CI.

## Taskfile — the command surface

`task --list` shows everything. Static tasks span BOTH services; tests run per
service or together.

| Task | Does |
|---|---|
| `task check` | Static gate: lint + type + arch, both services (no Docker) |
| `task lint` / `task type` | ruff / mypy, both services |
| `task fmt` | ruff-format, both services |
| `task arch` | import-linter cross-context contract (litestar_backend) |
| `task test` | Full Docker gate (ruff + mypy + pytest), both services |
| `task test:backend` / `task test:event` | Full Docker gate, one service |
| `task be:unit` / `task be:flow` | Fast backend tests, no Docker |
| `task em:unit` / `task em:flow` | Fast microservice tests, no Docker |
| `task be:integration` / `be:e2e` / `em:*` | Slower tests (need Docker) |
| `task dev` | `docker compose up --build` (full stack, hot-reload) |
| `task prod` | Stack without the dev override |

Typical inner loop:

```bash
task be:unit     # fast feedback while editing the backend
task fmt         # before committing
task check       # static gate, both services
```

## pre-commit — the commit gate

Runs automatically on `git commit` (after `pre-commit install`), or on demand:

```bash
pre-commit run --all-files
```

| Hook | Scope | Runs |
|---|---|---|
| gitleaks | whole repo | secret scan on the diff |
| ruff / ruff-format / mypy (litestar_backend) | `src/litestar_backend/` | via that service's uv venv |
| ruff / ruff-format / mypy (event_microservice) | `src/event_microservice/` | via that service's uv venv |

The ruff/mypy hooks are **local** — they call each service's own `uv run ruff/mypy`,
not pinned mirror hooks, so they always match `task lint` / `task type` and can
never drift from the toolchain pins above. gitleaks is a standalone scanner, pinned
by tag.

Notes:
- You cannot bypass the gate with `git commit --no-verify` — a repo hook blocks it.
  Fix the finding instead (`task fmt` for formatting), then re-commit.
- Stale hook tag? `pre-commit autoupdate`.
- A broken `task arch` is a real S-DDD violation (one bounded context importing
  another's internals); route it through `shared/` or an ACL.

## CI

No CI workflow ships yet. When added, it runs `task check` +
`pre-commit run --all-files` + `task test`. Until then these are local gates.

## Feature workflow

Every non-trivial change walks the same path, docs at both ends:

1. **Frame the feature.** State the goal and the boundary in a few lines:
   which bounded context owns it, what crosses the wire, what is out of
   scope.
2. **Read the docs first.** [architecture.md](architecture.md), the owning
   context's page under `src/<svc>/docs/contexts/`, the relevant
   `docs/contract/` pages, and any ADR that already constrains the area.
3. **Write the design.** A short spec: data flow, layer placement, new or
   changed wire shapes, error cases. New decision -> new ADR (<=40 lines).
4. **Read the code.** The owning context end-to-end plus the nearest
   analog (`media_example` is the golden reference) — plan the
   implementation against what actually exists, not against memory.
5. **Implement.** Domain first, then app, ports, adapters; tests at each
   level as you go (`unit -> flow -> integration -> e2e`).
6. **Update every touched doc in the same change.** Context page, contract
   page on any wire change, ADR status, env templates for new vars. A
   stale doc is a bug — the gate is not green until the docs match.

## Pointers

- [architecture.md](architecture.md) — layers, error hierarchy, DI, invariants.
- [glossary.md](glossary.md) — S-DDD terms in one place.
