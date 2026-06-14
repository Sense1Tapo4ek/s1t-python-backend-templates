DROP INDEX IF EXISTS media.ix_videos_keyset;
CREATE INDEX ix_videos_uploaded_at ON media.videos (uploaded_at DESC);
