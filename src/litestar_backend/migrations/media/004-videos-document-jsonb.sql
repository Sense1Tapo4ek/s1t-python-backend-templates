ALTER TABLE media.videos
    ADD COLUMN document JSONB NOT NULL DEFAULT '{}'::jsonb;

-- GIN index enables containment (@>) and key/field lookups on the document.
CREATE INDEX ix_videos_document ON media.videos USING gin (document);
