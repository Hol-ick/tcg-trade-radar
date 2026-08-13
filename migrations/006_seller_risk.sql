ALTER TABLE kaitori_sources ADD COLUMN seller_id TEXT;
ALTER TABLE kaitori_sources ADD COLUMN identity_scope TEXT NOT NULL DEFAULT 'post';
ALTER TABLE kaitori_sources ADD COLUMN post_family_id TEXT;
ALTER TABLE kaitori_sources ADD COLUMN listing_fingerprint TEXT;
ALTER TABLE kaitori_sources ADD COLUMN repost_of_source_id TEXT;
ALTER TABLE kaitori_sources ADD COLUMN is_repost INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS kaitori_sellers (
  seller_id TEXT PRIMARY KEY,
  gallery_id TEXT NOT NULL,
  display_name TEXT NOT NULL DEFAULT '',
  author_type TEXT NOT NULL DEFAULT 'unknown',
  identity_scope TEXT NOT NULL DEFAULT 'post',
  first_seen_at TEXT NOT NULL DEFAULT '',
  last_seen_at TEXT NOT NULL DEFAULT '',
  observed_post_count INTEGER NOT NULL DEFAULT 0,
  sell_post_count INTEGER NOT NULL DEFAULT 0,
  buy_post_count INTEGER NOT NULL DEFAULT 0,
  completed_post_count INTEGER NOT NULL DEFAULT 0,
  repost_count INTEGER NOT NULL DEFAULT 0,
  risk_score INTEGER NOT NULL DEFAULT 0,
  risk_level TEXT NOT NULL DEFAULT 'low',
  review_status TEXT NOT NULL DEFAULT 'unreviewed',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kaitori_risk_signals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  seller_id TEXT NOT NULL REFERENCES kaitori_sellers(seller_id),
  source_id TEXT NOT NULL REFERENCES kaitori_sources(id),
  code TEXT NOT NULL,
  severity TEXT NOT NULL,
  score_delta INTEGER NOT NULL DEFAULT 0,
  message TEXT NOT NULL,
  evidence_text TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (seller_id, source_id, code)
);

CREATE TABLE IF NOT EXISTS kaitori_seller_reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  seller_id TEXT NOT NULL REFERENCES kaitori_sellers(seller_id),
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  evidence_url TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS kaitori_sources_seller_idx ON kaitori_sources(seller_id, posted_at);
CREATE INDEX IF NOT EXISTS kaitori_risk_seller_idx ON kaitori_risk_signals(seller_id, status, id);
