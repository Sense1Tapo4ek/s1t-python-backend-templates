# yoyo-migrations

Version: per `pyproject.toml`. Documentation:
<https://ollycope.com/software/yoyo/latest/>.

Pip package, no external binary. SQL migrations applied at lifespan
start.

## Layout

Migrations mirror the bounded-context structure. Each context owns its
directory under `migrations/`:

```
migrations/
├── admin_log/
│   └── 0001_init.sql
└── <other_context>/
    └── 0001_init.sql
```

`migrations/<context>/` ↔ `src/<context>/`.

## File format

- Plain SQL, numbered `NNNN_snake_case.sql`.
- One migration per file; applied in a single transaction.
- Optional rollback: `-- !rollback:` block per yoyo conventions, or a
  separate `.rollback.sql` file.

## Application

Migrations run at context lifespan start, before the runtime
`SQLiteConnection` opens.

```python
from yoyo import read_migrations, get_backend

backend = get_backend(
    f"sqlite:///{db_path}",
    migration_table="_yoyo_admin_log",
)
migrations = read_migrations(str(migrations_dir))
with backend.lock():
    backend.apply_migrations(backend.to_apply(migrations))
```

## Tracking table convention

When multiple contexts share one database, each sets a unique
`migration_table` named `_yoyo_<context>` to isolate revision tracking.

`admin_log` defines the value once in
`src/admin/log/config.py::YOYO_MIGRATION_TABLE = "_yoyo_admin_log"` —
re-import; never duplicate the literal.

For separate per-context databases, the default `_yoyo_migration` works
but the `_yoyo_<context>` convention stays for consistency.

## Manual operations

```bash
# Apply pending
yoyo apply --database sqlite:///storage/logs/admin_logs.db migrations/admin_log/

# Roll back the last migration
yoyo rollback --database sqlite:///storage/logs/admin_logs.db migrations/admin_log/

# Show status
yoyo list --database sqlite:///storage/logs/admin_logs.db migrations/admin_log/
```

## Rules

- **Append-only.** Never edit a file that has been applied in any
  environment. Add a new file instead.
- **One logical change per migration.** Schema and matching data
  backfill belong together.
- **Idempotent at the apply level.** yoyo tracks applied state; the SQL
  itself need not be re-runnable.
- **Heavy backfills in chunks.** `UPDATE … WHERE id BETWEEN ? AND ?` to
  avoid long write locks.

## Adding a context that needs a database

1. Create `migrations/<context>/0001_init.sql`.
2. Set a unique `migration_table` in the context's `config.py`:
   `YOYO_MIGRATION_TABLE = "_yoyo_<context>"`.
3. Wire migration application into the context's lifespan manager
   (mirror the pattern in `admin/log/adapters/lifespan/`).

## Pointers

- Code: `src/admin/log/adapters/lifespan/`,
  `src/admin/log/config.py::YOYO_MIGRATION_TABLE`.
- Schema example: `migrations/admin_log/0001_init.sql`.
- yoyo docs: <https://ollycope.com/software/yoyo/latest/>
