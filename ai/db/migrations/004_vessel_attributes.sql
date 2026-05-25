-- 004_vessel_attributes.sql
-- Adds columns to lift Skipaskra raw data into proper queryable fields.
-- Idempotent.

ALTER TABLE vessels ADD COLUMN IF NOT EXISTS material        VARCHAR(40);  -- Eik=wood, Stál=steel, Ál=aluminium, plast=fibreglass (Trefja-plast truncated by parser)
ALTER TABLE vessels ADD COLUMN IF NOT EXISTS engine_maker    VARCHAR(80);  -- Volvo Penta / Caterpillar / Cummins / etc
ALTER TABLE vessels ADD COLUMN IF NOT EXISTS depth_m         REAL;

CREATE INDEX IF NOT EXISTS idx_vessels_material ON vessels(material);
CREATE INDEX IF NOT EXISTS idx_vessels_home_port ON vessels(home_port);

-- Verify after apply:
--   SELECT material, count(*) FROM vessels GROUP BY material ORDER BY count DESC;
