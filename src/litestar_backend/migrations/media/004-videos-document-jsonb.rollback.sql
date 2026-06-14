DROP INDEX IF EXISTS media.ix_videos_document;
ALTER TABLE media.videos DROP COLUMN IF EXISTS document;
