DROP INDEX IF EXISTS media.ix_videos_active_keyset;
CREATE INDEX ix_videos_keyset ON media.videos (uploaded_at DESC, id DESC);
ALTER TABLE media.videos
    DROP COLUMN IF EXISTS deleted_at,
    DROP COLUMN IF EXISTS updated_at,
    DROP COLUMN IF EXISTS created_at;
