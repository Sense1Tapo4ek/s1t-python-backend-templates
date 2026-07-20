CREATE TABLE auth.outbox_messages (
    id         UUID PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload    BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at    TIMESTAMPTZ NULL
);

CREATE INDEX ix_auth_outbox_pending ON auth.outbox_messages (created_at) WHERE sent_at IS NULL;
