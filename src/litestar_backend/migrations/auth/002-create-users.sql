CREATE TABLE auth.users (
    id            UUID PRIMARY KEY,
    email         TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ NULL
);

-- One ACTIVE account per email; login looks up by email WHERE deleted_at IS
-- NULL, so the partial unique index both enforces uniqueness and serves the
-- lookup. A deactivated row keeps its email on disk for audit.
CREATE UNIQUE INDEX ix_users_active_email
    ON auth.users (email)
    WHERE deleted_at IS NULL;

-- Keyset pagination for the admin list: ORDER BY created_at DESC, id DESC
-- over active rows only.
CREATE INDEX ix_users_active_keyset
    ON auth.users (created_at DESC, id DESC)
    WHERE deleted_at IS NULL;
