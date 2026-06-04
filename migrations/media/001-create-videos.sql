CREATE SCHEMA IF NOT EXISTS media;

CREATE TABLE media.videos (
    id          UUID PRIMARY KEY,
    source_key  TEXT NOT NULL,
    status      TEXT NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX ix_videos_uploaded_at ON media.videos (uploaded_at DESC);

CREATE TABLE media.outbox_messages (
    id         UUID PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload    BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at    TIMESTAMPTZ NULL
);
CREATE INDEX ix_outbox_pending ON media.outbox_messages (created_at) WHERE sent_at IS NULL;
