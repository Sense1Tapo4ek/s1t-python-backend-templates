ALTER TABLE media.videos
    ADD COLUMN document JSONB NOT NULL DEFAULT '{}'::jsonb;

-- GIN index (jsonb_ops) accelerates containment (@>) and key-existence
-- (?, ?|, ?&) queries -- NOT ->> field extraction, which needs a functional
-- B-tree index on the specific key. list_by_content_type uses @> so it can use
-- this index.
CREATE INDEX ix_videos_document ON media.videos USING gin (document);
