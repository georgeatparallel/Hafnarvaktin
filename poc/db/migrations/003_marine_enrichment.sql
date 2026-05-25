-- 003_marine_enrichment.sql
-- Adds columns for live registry refresh (island.is shipRegistryShipSearch)
-- and GFW vessel enrichment. Idempotent.

-- island.is fields not already present in vessels:
ALTER TABLE vessels ADD COLUMN IF NOT EXISTS reg_status      VARCHAR(60);  -- "Á aðalskipaskrá" etc.
ALTER TABLE vessels ADD COLUMN IF NOT EXISTS manufactor_year INTEGER;       -- Built year, distinct from raw->>'year_built'
ALTER TABLE vessels ADD COLUMN IF NOT EXISTS manufacturer    VARCHAR(200);
ALTER TABLE vessels ADD COLUMN IF NOT EXISTS opid            VARCHAR(60);   -- island.is operator id

-- GFW fields:
ALTER TABLE vessels ADD COLUMN IF NOT EXISTS gfw_vessel_id   VARCHAR(40);
ALTER TABLE vessels ADD COLUMN IF NOT EXISTS gear_type       VARCHAR(60);  -- TRAWLERS / SET_GILLNETS / etc
ALTER TABLE vessels ADD COLUMN IF NOT EXISTS ais_last_seen   TIMESTAMP;     -- transmissionDateTo

CREATE INDEX IF NOT EXISTS idx_vessels_gfw_id ON vessels(gfw_vessel_id);
CREATE INDEX IF NOT EXISTS idx_vessels_call_sign ON vessels(call_sign);

-- Owners: separate table since one vessel can have multiple owners + share
-- percentages. Keeps the parent row simple.
CREATE TABLE IF NOT EXISTS vessel_owners (
    id              SERIAL PRIMARY KEY,
    vessel_id       INTEGER NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
    name            VARCHAR(200),
    national_id     VARCHAR(20),       -- kennitala (anonymise if exposing)
    share_percent   REAL,
    source          VARCHAR(40) NOT NULL,
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (vessel_id, name, source)
);

CREATE INDEX IF NOT EXISTS idx_vessel_owners_vessel ON vessel_owners(vessel_id);

-- Refresh log entry per vessel ID, so a re-run is incremental.
ALTER TABLE vessels ADD COLUMN IF NOT EXISTS islandis_refreshed_at TIMESTAMP;
ALTER TABLE vessels ADD COLUMN IF NOT EXISTS gfw_resolved_at       TIMESTAMP;

-- Verify
-- \d vessels
-- \d vessel_owners
