CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE auth.api_keys (
    id         UUID PRIMARY KEY,
    key_hash   TEXT NOT NULL,
    name       TEXT NOT NULL,
    role       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ NULL
);

-- One ACTIVE key per hash; the resolver looks up by key_hash WHERE deleted_at
-- IS NULL, so this partial unique index both enforces uniqueness and serves
-- the lookup. A revoked row keeps its hash on disk for audit.
CREATE UNIQUE INDEX ix_api_keys_active_hash
    ON auth.api_keys (key_hash)
    WHERE deleted_at IS NULL;
