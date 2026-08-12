-- Canonical schema is embedded in kaitori_collector.storage.SCHEMA_SQL so the
-- standard-library worker can initialize a fresh SQLite file without a tool.
-- This file mirrors the table contract for review and future migrations.

CREATE TABLE kaitori_sources (
  id TEXT PRIMARY KEY,
  gallery_id TEXT NOT NULL,
  post_id TEXT,
  post_url TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  posted_at TEXT NOT NULL DEFAULT '',
  raw_html TEXT,
  fetched_at TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  UNIQUE (post_url, content_hash)
);

CREATE TABLE kaitori_jobs (
  id TEXT PRIMARY KEY,
  gallery_id TEXT NOT NULL,
  subject TEXT NOT NULL,
  since TEXT,
  until TEXT,
  buy_rate INTEGER NOT NULL,
  state TEXT NOT NULL,
  counts TEXT NOT NULL DEFAULT '{}',
  error_message TEXT,
  created_at TEXT NOT NULL,
  finished_at TEXT,
  worker_version TEXT NOT NULL,
  last_success_at TEXT,
  config_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE kaitori_rows (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES kaitori_jobs(id),
  source_id TEXT NOT NULL REFERENCES kaitori_sources(id),
  row_fingerprint TEXT NOT NULL,
  card_name_raw TEXT NOT NULL DEFAULT '',
  card_code TEXT NOT NULL DEFAULT '',
  rarity TEXT NOT NULL DEFAULT '',
  raw_price TEXT NOT NULL DEFAULT '',
  price_krw INTEGER NOT NULL DEFAULT 0,
  price_unit TEXT NOT NULL DEFAULT '',
  quantity INTEGER NOT NULL DEFAULT 1,
  shipping_included TEXT NOT NULL,
  shipping_price_krw INTEGER,
  status TEXT NOT NULL,
  review_reason TEXT NOT NULL DEFAULT '',
  raw_line TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_id, row_fingerprint)
);

CREATE TABLE kaitori_job_sources (
  job_id TEXT NOT NULL REFERENCES kaitori_jobs(id),
  source_id TEXT NOT NULL REFERENCES kaitori_sources(id),
  created_at TEXT NOT NULL,
  PRIMARY KEY (job_id, source_id)
);

CREATE TABLE kaitori_job_rows (
  job_id TEXT NOT NULL REFERENCES kaitori_jobs(id),
  row_id TEXT NOT NULL REFERENCES kaitori_rows(id),
  created_at TEXT NOT NULL,
  PRIMARY KEY (job_id, row_id)
);

CREATE TABLE kaitori_matches (
  row_id TEXT NOT NULL REFERENCES kaitori_rows(id),
  catalog_card_id TEXT NOT NULL,
  confidence REAL NOT NULL,
  matched_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (row_id, catalog_card_id)
);

CREATE TABLE kaitori_reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  row_id TEXT NOT NULL REFERENCES kaitori_rows(id),
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  before_data TEXT NOT NULL,
  after_data TEXT NOT NULL,
  created_at TEXT NOT NULL
);
