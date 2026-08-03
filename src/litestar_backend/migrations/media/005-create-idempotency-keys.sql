-- Idempotency keys for POST /videos. The key claim commits in the SAME
-- transaction as the video row and its outbox row, so a committed key always
-- names a committed effect; a duplicate request replays `response` instead of
-- creating a second video.
CREATE TABLE media.idempotency_keys (
    key         TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    response    JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL
);

-- Supports the retention sweep (DELETE ... WHERE expires_at < now()).
CREATE INDEX ix_idempotency_keys_expires_at ON media.idempotency_keys (expires_at);
