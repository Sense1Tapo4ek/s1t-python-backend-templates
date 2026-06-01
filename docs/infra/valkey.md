# Valkey

Backs the **metrics** subsystem only. Cross-worker metric snapshots (RSS,
event-loop lag, per-worker counters) are written to Valkey hashes by each
worker and merged on every `/metrics` scrape. Logs do NOT use Valkey.

For *why* metrics need a shared store, see
[subsystems/metrics.md](../subsystems/metrics.md).

## Version

`valkey/valkey:8-alpine`. Redis-protocol compatible, so `redis-py` works
unmodified.

## Configuration

| Env | Default | Owner | Notes |
|:---|:---|:---|:---|
| `VALKEY_URL` | `redis://localhost:6379/0` | `shared/config.py` | Required by the metrics subsystem. |
| `METRICS_KEY_PREFIX` | `metrics:` | `admin/metrics/config.py` | Hash key prefix for per-worker snapshots. |
| `METRICS_KEY_TTL_S` | `30` | `admin/metrics/config.py` | TTL so a dead worker's hash expires. |

The Compose service runs with `--appendonly no --save 60 1000
--maxmemory-policy noeviction`. Snapshots are sacrificial and TTL-bounded;
RDB is enough for planned restarts.

## Where it touches the code

| Use | File |
|:---|:---|
| Per-worker snapshot write / read | `src/admin/metrics/ports/driven/` (Valkey hash provider) |
| Compose service | `docker-compose.yml` |

## Operational notes

- If Valkey is down, per-worker counters still serve (they live in the local
  `prometheus_client.REGISTRY`); only cross-worker snapshots degrade.
- A single Valkey instance is enough for the template.

## Pointers

- Subsystem: [subsystems/metrics.md](../subsystems/metrics.md)
- Vendor docs: <https://valkey.io/topics/>
