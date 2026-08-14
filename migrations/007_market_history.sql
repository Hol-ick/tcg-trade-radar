-- Graph-ready market history for existing SQLite databases.
ALTER TABLE kaitori_demand_snapshots ADD COLUMN snapshot_at TEXT NOT NULL DEFAULT '';
ALTER TABLE kaitori_demand_snapshots ADD COLUMN range_since TEXT NOT NULL DEFAULT '';
ALTER TABLE kaitori_demand_snapshots ADD COLUMN range_until TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS kaitori_market_observations (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES kaitori_sources(id),
  row_id TEXT NOT NULL REFERENCES kaitori_rows(id),
  gallery_id TEXT NOT NULL,
  card_key TEXT NOT NULL DEFAULT '',
  card_name_raw TEXT NOT NULL DEFAULT '',
  card_name_normalized TEXT NOT NULL DEFAULT '',
  card_code TEXT NOT NULL DEFAULT '',
  seller_id TEXT,
  listing_type TEXT NOT NULL DEFAULT 'unknown',
  quantity INTEGER NOT NULL DEFAULT 1,
  price_krw_observed INTEGER,
  price_status TEXT NOT NULL DEFAULT 'unknown',
  price_scope TEXT NOT NULL DEFAULT 'unknown',
  price_origin TEXT NOT NULL DEFAULT 'unknown',
  analysis_status TEXT NOT NULL DEFAULT 'needs_review',
  review_status TEXT NOT NULL DEFAULT 'needs_review',
  review_reason TEXT NOT NULL DEFAULT '',
  card_match_status TEXT NOT NULL DEFAULT 'unmatched',
  post_status TEXT NOT NULL DEFAULT 'active',
  source_status TEXT NOT NULL DEFAULT 'active',
  is_repost INTEGER NOT NULL DEFAULT 0,
  posted_at TEXT NOT NULL DEFAULT '',
  event_date TEXT NOT NULL DEFAULT '',
  observed_at TEXT NOT NULL DEFAULT '',
  observed_date TEXT NOT NULL DEFAULT '',
  source_content_hash TEXT NOT NULL DEFAULT '',
  source_fetched_at TEXT NOT NULL DEFAULT '',
  normalization_version TEXT NOT NULL DEFAULT 'listing-label-v2',
  created_at TEXT NOT NULL,
  UNIQUE(source_id, row_id)
);

CREATE INDEX IF NOT EXISTS kaitori_market_observation_event_idx
  ON kaitori_market_observations(gallery_id, card_key, event_date, observed_date);
CREATE INDEX IF NOT EXISTS kaitori_market_observation_observed_idx
  ON kaitori_market_observations(gallery_id, card_key, observed_date, listing_type);

CREATE TABLE IF NOT EXISTS kaitori_market_daily (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  gallery_id TEXT NOT NULL,
  card_key TEXT NOT NULL,
  card_name_raw TEXT NOT NULL DEFAULT '',
  event_date TEXT NOT NULL DEFAULT '',
  observed_date TEXT NOT NULL,
  supply_listing_count INTEGER NOT NULL DEFAULT 0,
  demand_listing_count INTEGER NOT NULL DEFAULT 0,
  trade_listing_count INTEGER NOT NULL DEFAULT 0,
  supply_post_count INTEGER NOT NULL DEFAULT 0,
  demand_post_count INTEGER NOT NULL DEFAULT 0,
  trade_post_count INTEGER NOT NULL DEFAULT 0,
  supply_quantity INTEGER NOT NULL DEFAULT 0,
  demand_quantity INTEGER NOT NULL DEFAULT 0,
  trade_quantity INTEGER NOT NULL DEFAULT 0,
  supply_price_count INTEGER NOT NULL DEFAULT 0,
  demand_price_count INTEGER NOT NULL DEFAULT 0,
  supply_price_median INTEGER,
  supply_price_min INTEGER,
  supply_price_max INTEGER,
  demand_price_median INTEGER,
  demand_price_min INTEGER,
  demand_price_max INTEGER,
  source_count INTEGER NOT NULL DEFAULT 0,
  seller_count INTEGER NOT NULL DEFAULT 0,
  matched_listing_count INTEGER NOT NULL DEFAULT 0,
  candidate_listing_count INTEGER NOT NULL DEFAULT 0,
  unmatched_listing_count INTEGER NOT NULL DEFAULT 0,
  review_count INTEGER NOT NULL DEFAULT 0,
  quality_status TEXT NOT NULL DEFAULT 'needs_review',
  created_at TEXT NOT NULL,
  UNIQUE(gallery_id, card_key, event_date, observed_date)
);

CREATE INDEX IF NOT EXISTS kaitori_market_daily_event_idx
  ON kaitori_market_daily(gallery_id, card_key, event_date, observed_date);
CREATE INDEX IF NOT EXISTS kaitori_market_daily_observed_idx
  ON kaitori_market_daily(gallery_id, card_key, observed_date);
