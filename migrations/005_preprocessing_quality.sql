-- Quality metadata for noisy trade posts. Raw HTML remains in kaitori_sources.
ALTER TABLE kaitori_sources ADD COLUMN post_status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE kaitori_sources ADD COLUMN image_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE kaitori_sources ADD COLUMN body_characters INTEGER NOT NULL DEFAULT 0;

ALTER TABLE kaitori_rows ADD COLUMN price_krw_observed INTEGER;
ALTER TABLE kaitori_rows ADD COLUMN post_status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE kaitori_rows ADD COLUMN price_status TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE kaitori_rows ADD COLUMN price_scope TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE kaitori_rows ADD COLUMN price_origin TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE kaitori_rows ADD COLUMN analysis_status TEXT NOT NULL DEFAULT 'needs_review';
ALTER TABLE kaitori_rows ADD COLUMN card_match_status TEXT NOT NULL DEFAULT 'unmatched';
