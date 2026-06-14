ALTER TABLE media.videos
    ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN deleted_at TIMESTAMPTZ NULL;

-- Reads filter deleted_at IS NULL; a partial keyset index serves only active
-- rows and replaces the full ix_videos_keyset from migration 002.
-- On a production table with live traffic, build the index with CREATE INDEX
-- CONCURRENTLY (no ShareLock) -- which yoyo cannot do inside its transaction;
-- it would need a separate transaction-less migration. Plain CREATE INDEX is
-- fine here (index built at lifespan startup before traffic).
DROP INDEX IF EXISTS media.ix_videos_keyset;
CREATE INDEX ix_videos_active_keyset
    ON media.videos (uploaded_at DESC, id DESC)
    WHERE deleted_at IS NULL;
