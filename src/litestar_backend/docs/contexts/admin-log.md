# admin/log

File-tail log viewer: read the rotating JSONL file the app writes, show it
live and historically in the admin UI. Sub-context of [admin](admin.md).

For the *why*, see [adr/0009-file-tail-log-viewer.md](../adr/0009-file-tail-log-viewer.md).

## Mental model

structlog renders every record as one JSON object on one line and writes it
to two handlers: `stdout` (12-factor capture) and a `WatchedFileHandler` at
`LOG_FILE_PATH` (the source of truth for the UI). There is no database, no
queue, no second process, no Valkey on this path.

```
log.info("user paid", ...)
       |
       v
structlog -> JSON line --+--> StreamHandler  -> stdout
                         +--> WatchedFileHandler -> app.jsonl
                                                       |
                                  external rotation (logrotate / docker)
                                                       v
                              FileLogReader (ports/driven)
                              read_tail / read_before / stream_all / follow
                                                       |
                              facade -> use cases -> controller
                                  |                          |
        GET /api/v1/admin/logs (tail N)         GET .../stream (SSE, follow)
                                  |
                          static/admin/log (UI)
          level filter . substring . load more . drilldown  (client-side)
```

History (`read_tail`, `read_before`) and live tail (`follow`) both read the
same file. Rotation is external; the reader follows `tail -F` semantics.

## Public surface

### Endpoints

| Path | Method | Purpose |
|:---|:---|:---|
| `/admin/logs` | GET | HTML viewer (`Template`). |
| `/api/v1/admin/logs` | GET | Tail page: `{entries, cursor}` (last `LOG_TAIL_LINES`). |
| `/api/v1/admin/logs/older` | GET | Older page; `cursor=<base64>` from a previous page. |
| `/api/v1/admin/logs/stream` | GET | Server-Sent Events live tail (`ServerSentEvent`). |
| `/api/v1/admin/logs/export` | GET | Stream the file as a download; `format=ndjson\|csv`. |

All require `Role.ADMIN`.

### Types

| Symbol | Where | Role |
|:---|:---|:---|
| `LogsFacade` | `ports/driving/logs_facade.py` | render / older / stream / export. Thin. |
| `ILogReader` | `app/interfaces/` | `read_tail`, `read_before`, `stream_all`. |
| `ILogFollower` | `app/interfaces/` | `follow(poll_ms)` — yields appended entries. |
| `FileLogReader` | `ports/driven/file_log_reader.py` | implements both; maps lines, owns cursor. |
| `LogFileSource` | `adapters/driven/log_file_source.py` | raw I/O: open, stat, reverse-read, rotation. |
| `LogEntryEnt` | `domain/` | parsed line: `timestamp, level, logger, event, raw`. |
| `Cursor` | `domain/types.py` | `(inode, offset)`; base64 on the wire. |
| `LogEntrySchema`, `LogPageResponseSchema` | `ports/driving/log_schemas.py` | wire: `entries`, `cursor`. |

## Cursor semantics

A `Cursor` is `(inode, offset)`: the inode of the live file and the byte
offset of the first line in the page. On the wire it is base64 of
`"inode:offset"`, opaque to the client. `read_before` reads `limit` lines
ending just before `offset`. If the inode no longer matches the live file
(rotation happened), back-scroll stops: the page returns `cursor=null`
("history truncated by rotation"), and the UI disables "load more". A null
cursor also means the start of the file is reached.

## UI features

All client-side except "load more":

- **Level chips** — filter the loaded rows by level.
- **Substring search** — case-insensitive match over event, logger, level,
  and serialised context of the loaded rows.
- **Load more** — calls `/older?cursor=` to pull `LOG_LOAD_MORE_LINES` more
  lines from the file; they then become filterable.
- **Drilldown** — expand a row to see Context / JSON / Exception.

Live frames arrive via SSE and prepend to the top. Entries are de-duplicated
client-side by `(timestamp, logger, event)` — file-tail lines have no id.

## Configuration

`admin/log/config.py`, prefix `LOG_`:

| Var | Default | Meaning |
|:---|:---|:---|
| `LOG_FILE_PATH` | `${VOLUME_PATH}/logs/app.jsonl` | File both handlers and the reader use. |
| `LOG_TAIL_LINES` | `200` | Lines in the initial tail page. |
| `LOG_LOAD_MORE_LINES` | `200` | Lines per "load more" page. |
| `LOG_FOLLOW_POLL_MS` | `250` | Poll interval for `follow` (live tail). |
| `LOG_MAX_LINE_BYTES` | `65536` | Write-side line cap; reader skips longer lines. |

## Invariants & gotchas

- **One JSON object per line (JSONL).** The reader treats each `\n`-delimited
  line as one record. The write-side guarantee that keeps it so (line
  truncation to `LOG_MAX_LINE_BYTES`, `O_APPEND` single-write atomicity) lives
  in [infra/structlog.md](../infra/structlog.md).
- **Trailing partial line is not a line.** Bytes after the last `\n` are
  discarded by the reader; `follow` advances only past a confirmed `\n`.
  Prevents torn JSON and corrupt cursors during a concurrent append.
- **Malformed lines are skipped.** `LogEntryEnt.parse` raises
  `MalformedLogLine` (a `DomainError`); the port catches it per line, skips,
  and counts. The optional warning is logged in the adapter only — ports
  never log.
- **Missing/unreadable file -> `LogReadError`** (a `PortError`, 503).
- **Live tail is best-effort across rotation.** On size-shrink
  (`copytruncate`) or inode change (`create`), `follow` drains the old fd to
  EOF, then reopens. Entries written in the gap may be missed (at-most-once).
- **Export is a point-in-time snapshot.** `ExportLogsUc` opens the file once
  and streams the held fd to EOF; it does not re-stat or reopen. Use
  `create`-mode rotation (not `copytruncate`) so the held fd reads a
  consistent inode.
- **Filters are client-side.** Level chips and substring search apply only to
  rows already loaded in the browser. "Load more" widens the loaded set.

## Recipes

### Point the UI at a different file

```
LOG_FILE_PATH=/var/log/myapp/app.jsonl
```

The writer (structlog handler) and the reader share this one path.

### Rotate the file

External only. Example logrotate config ships in `deploy/logrotate/app.conf`
using `create`-mode (see [infra/structlog.md](../infra/structlog.md)). The
app never deletes the file it writes.

### Replace the front-end

Assets live at `static/admin/log/{index.html,style.css,tail.js}` and are
served from the single `/static/` mount. The controller returns
`Template("admin/log/index.html")`.

## Pointers

- ADR: [adr/0009-file-tail-log-viewer.md](../adr/0009-file-tail-log-viewer.md)
- Code: `src/admin/log/`
- structlog pipeline: [infra/structlog.md](../infra/structlog.md)
- Cross-cutting: [subsystems/observability.md](../subsystems/observability.md)
