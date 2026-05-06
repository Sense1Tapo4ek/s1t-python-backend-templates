# admin

Operator-facing dashboard shell: login flow, dashboard overview, build-info
panel, health/readiness probes.

For the log subsystem (data, search, export), see
[contexts/admin-log.md](admin-log.md).

## Mental model

`admin` owns the HTML dashboard frame and public diagnostic endpoints
(`/health`, `/ping`). The log feature lives as a sub-context at
`src/admin/log/` so it can grow without bloating the parent.

```
src/admin/
├── adapters/driving/api/
│   ├── health_controller.py     # /health, /health/ready, /ping
│   ├── login_controller.py      # /admin/login, /admin/logout
│   └── admin_controller.py      # /admin/  (dashboard)
├── domain/                      # BuildInfoVo
└── log/                         # sub-context — see admin-log.md
```

## Public surface

| Endpoint | Method | Auth | Purpose |
|:---|:---|:---|:---|
| `/health` | GET | none | Liveness; returns `BuildInfoVo` JSON. |
| `/health/ready` | GET | none | Readiness; runs `SELECT 1` against the SQLite reader pool. 503 on failure. |
| `/ping` | GET | none | Minimal heartbeat (sync handler). |
| `/admin/login` | GET | none | Renders the login form. |
| `/admin/login` | POST | none | Validates token, sets cookie, 303 → `next`. |
| `/admin/logout` | POST | none | Clears cookie, 303 → `/admin/login`. |
| `/admin/` | GET | `ADMIN` | Dashboard overview + build info panel. |

## Build info

`BuildInfoVo(app_name, started_at, commit_sha, branch, dirty)` is built
once at startup by `admin/adapters/driven/build_info/git_build_info.py`.

Resolution order:
1. **Env vars** — if `GIT_COMMIT_SHA` is set, use it together with
   `GIT_BRANCH` and `GIT_DIRTY`. Docker/CI path.
2. **`git` subprocess** — `git rev-parse HEAD`, `--abbrev-ref HEAD`,
   `git status --porcelain`. Dev checkout path.
3. **Fallback** — `commit_sha="unknown"`, `branch=None`, `dirty=False`.

`/health` response:

```json
{
  "status": "ok",
  "app": "litestar-base",
  "commit": "deadbeef1234abcd...",
  "branch": "main",
  "dirty": false,
  "started_at": "2026-05-06T13:11:05.890306+00:00"
}
```

## Two-tier health

Kubernetes-style separation:
- `/health` → liveness. Always 200 while the process is alive. Failing
  this restarts the pod.
- `/health/ready` → readiness. 503 when the reader pool is unhealthy.
  Failing this removes the replica from the LB pool but does **not**
  trigger a restart.

## CI/Docker setup for build info

```dockerfile
ARG GIT_COMMIT_SHA
ARG GIT_BRANCH
ARG GIT_DIRTY
ENV GIT_COMMIT_SHA=${GIT_COMMIT_SHA} \
    GIT_BRANCH=${GIT_BRANCH} \
    GIT_DIRTY=${GIT_DIRTY}
```

```bash
docker build \
  --build-arg GIT_COMMIT_SHA=$(git rev-parse HEAD) \
  --build-arg GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD) \
  --build-arg GIT_DIRTY=$([ -n "$(git status --porcelain)" ] && echo 1 || echo 0) \
  -t myapp .
```

GitHub Actions:

```yaml
env:
  GIT_COMMIT_SHA: ${{ github.sha }}
  GIT_BRANCH: ${{ github.ref_name }}
  GIT_DIRTY: 0
```

## Invariants & gotchas

- `path = ""` on `HealthController` so `/health` and `/ping` sit at root,
  not under `/admin/`.
- The dashboard at `/admin/` requires the `ADMIN` role; the login flow
  itself does not (it'd be unreachable otherwise).
- `BuildInfoVo` is a single VO because all five fields describe one process
  instance — splitting per field is noise.

## Pointers

- Code: `src/admin/adapters/driving/api/`
- Auth: [contexts/auth.md](auth.md)
- Log subsystem: [contexts/admin-log.md](admin-log.md)
