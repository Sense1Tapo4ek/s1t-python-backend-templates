# Contributing

## Setup

```bash
cd src/litestar_backend  && uv sync
cd ../event_microservice && uv sync
uv tool install pre-commit && pre-commit install
```

## Before opening a PR

```bash
task check   # lint + type + arch, both services
task test    # full Docker gate (ruff + mypy + pytest), both services
```

Both must be green. CI runs the same gates.

## Rules

- Conventional commits: `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`.
- Behaviour change -> matching `docs/` page updated in the same PR. A stale
  doc is treated as a bug.
- Wire-shape change -> matching `docs/contract/` page in the same PR.
- New architectural decision -> new ADR (MADR, <=40 lines); never edit an
  accepted ADR, supersede it.
- Layer rules and context boundaries: [docs/architecture.md](docs/architecture.md).
  `task arch` must stay green.
- Tests mirror `src/` and follow the pyramid: unit (domain, no mocks), flow
  (mocked interfaces), integration (real infra), e2e (full app).

## Workflow details

See [docs/development.md](docs/development.md) -- toolchain, Taskfile surface,
pre-commit gate, feature workflow.
