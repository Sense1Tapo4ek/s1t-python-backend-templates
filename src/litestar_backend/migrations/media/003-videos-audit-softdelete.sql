ALTER TABLE media.videos
    ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN deleted_at TIMESTAMPTZ NULL;

-- Reads filter deleted_at IS NULL; a partial keyset index serves only active
-- rows and replaces the full ix_videos_keyset from migration 002.
DROP INDEX IF EXISTS media.ix_videos_keyset;
CREATE INDEX ix_videos_active_keyset
    ON media.videos (uploaded_at DESC, id DESC)
    WHERE deleted_at IS NULL;
