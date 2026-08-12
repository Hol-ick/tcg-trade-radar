-- Market explorer additions for existing SQLite databases.
ALTER TABLE kaitori_sources ADD COLUMN source_status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE kaitori_rows ADD COLUMN listing_type TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE kaitori_rows ADD COLUMN intent_confidence REAL NOT NULL DEFAULT 0;
ALTER TABLE kaitori_rows ADD COLUMN price_type TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE kaitori_rows ADD COLUMN set_name TEXT NOT NULL DEFAULT '';
ALTER TABLE kaitori_rows ADD COLUMN condition_raw TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS kaitori_demand_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_date TEXT NOT NULL,
  game_id TEXT NOT NULL,
  card_key TEXT NOT NULL,
  card_name_raw TEXT NOT NULL DEFAULT '',
  sell_count INTEGER NOT NULL DEFAULT 0,
  buy_count INTEGER NOT NULL DEFAULT 0,
  trade_count INTEGER NOT NULL DEFAULT 0,
  sell_price_median INTEGER,
  sell_price_min INTEGER,
  sell_price_max INTEGER,
  wanted_price_median INTEGER,
  active_source_count INTEGER NOT NULL DEFAULT 0,
  demand_score REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  UNIQUE(snapshot_date, game_id, card_key)
);
