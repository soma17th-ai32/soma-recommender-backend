CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS lectures (
    id BIGSERIAL PRIMARY KEY,
    source_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    detail_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    receipt_period TEXT,
    event_date TEXT,
    author TEXT,
    registered_at TEXT,
    content_hash TEXT NOT NULL,
    embedding vector(4096),
    embedding_updated_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lectures_status_idx
    ON lectures (status);

CREATE INDEX IF NOT EXISTS lectures_last_seen_at_idx
    ON lectures (last_seen_at);
