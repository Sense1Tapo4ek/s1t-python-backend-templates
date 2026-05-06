-- 0001_init.sql
-- Initial schema for admin_log context: logs table, indexes, FTS5 mirror, sync triggers.

CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    logger TEXT,
    event TEXT,
    pathname TEXT,
    lineno INTEGER,
    func_name TEXT,
    raw_json TEXT NOT NULL,
    trace_id TEXT,
    span_id TEXT
);

CREATE INDEX idx_logs_timestamp ON logs(timestamp);
CREATE INDEX idx_logs_event ON logs(event);
CREATE INDEX idx_logs_trace_id ON logs(trace_id);
-- Composite covering the dominant filter shape (level equality + timestamp
-- range). Column order matters: SQLite can still use the leftmost prefix
-- for level-only queries, so a separate single-column `idx_logs_level` is
-- redundant.
CREATE INDEX idx_logs_level_timestamp ON logs(level, timestamp);

-- detail='none' intentionally omitted: required for phrase queries with the
-- trigram tokenizer. Trade-off: ~2x FTS index storage vs. token-only search.
CREATE VIRTUAL TABLE logs_fts USING fts5(
    raw_json,
    content='logs',
    content_rowid='id',
    tokenize='trigram'
);

CREATE TRIGGER logs_ai AFTER INSERT ON logs BEGIN
    INSERT INTO logs_fts(rowid, raw_json) VALUES (new.id, new.raw_json);
END;

CREATE TRIGGER logs_ad AFTER DELETE ON logs BEGIN
    INSERT INTO logs_fts(logs_fts, rowid, raw_json) VALUES ('delete', old.id, old.raw_json);
END;
