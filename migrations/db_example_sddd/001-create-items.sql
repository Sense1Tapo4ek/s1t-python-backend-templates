CREATE SCHEMA IF NOT EXISTS db_example_sddd;
CREATE TABLE db_example_sddd.items (
    id          UUID PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL
);
