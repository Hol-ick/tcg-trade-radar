-- Public author markers and read-only comment records.
ALTER TABLE kaitori_sources ADD COLUMN author_name TEXT NOT NULL DEFAULT '';
ALTER TABLE kaitori_sources ADD COLUMN author_type TEXT NOT NULL DEFAULT 'unknown';

CREATE TABLE IF NOT EXISTS kaitori_comments (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES kaitori_sources(id),
  gallery_id TEXT NOT NULL,
  post_url TEXT NOT NULL,
  comment_id TEXT NOT NULL DEFAULT '',
  parent_id TEXT NOT NULL DEFAULT '',
  author_name TEXT NOT NULL DEFAULT '',
  author_type TEXT NOT NULL DEFAULT 'unknown',
  body TEXT NOT NULL DEFAULT '',
  posted_at TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  UNIQUE (source_id, comment_id, body)
);
