-- Stable keyset order needs a tiebreaker: (uploaded_at DESC, id DESC). The
-- single-column ix_videos_uploaded_at cannot page rows that share a timestamp.
DROP INDEX IF EXISTS media.ix_videos_uploaded_at;
CREATE INDEX ix_videos_keyset ON media.videos (uploaded_at DESC, id DESC);
