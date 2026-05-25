-- 002_marine_schema.sql
-- Adds the marine-data schema on top of the existing YOLO tables.
-- Apply once, after switching the image to pgvector/pgvector:pg17.
-- Idempotent (CREATE TABLE IF NOT EXISTS / CREATE EXTENSION IF NOT EXISTS).

-- pgvector for embedding columns (View C RAG).
CREATE EXTENSION IF NOT EXISTS vector;

-- ── vessels ────────────────────────────────────────────────────
-- One row per known vessel. IMO and MMSI are both possible IDs.
-- A vessel can exist with only one of them (e.g. Iceland-flagged
-- inshore boats may have no IMO; AIS-only sightings of foreign
-- vessels may have no Iceland-registered IMO).
CREATE TABLE IF NOT EXISTS vessels (
    id              SERIAL PRIMARY KEY,
    imo             VARCHAR(7)      UNIQUE,
    mmsi            BIGINT          UNIQUE,
    name            VARCHAR(200)    NOT NULL,
    name_normalised VARCHAR(200),
    call_sign       VARCHAR(20),
    flag_country    VARCHAR(3),
    type            VARCHAR(80),
    type_code       INTEGER,                     -- AIS shiptype 0-99
    length_m        REAL,
    beam_m          REAL,
    gt              INTEGER,                     -- gross tonnage
    home_port       VARCHAR(120),
    registration_no VARCHAR(40),                 -- Samgöngustofa skipsnúmer
    district_no     VARCHAR(40),                 -- umdæmisnúmer
    source          VARCHAR(40)     NOT NULL,    -- 'samgongustofa' | 'aisstream' | 'manual'
    source_id       VARCHAR(120),
    raw             JSONB,
    description     TEXT,
    description_embedding vector(768),
    first_seen      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vessels_name_norm ON vessels(name_normalised);
CREATE INDEX IF NOT EXISTS idx_vessels_imo ON vessels(imo);
CREATE INDEX IF NOT EXISTS idx_vessels_mmsi ON vessels(mmsi);

-- ── port_calls ─────────────────────────────────────────────────
-- Arrivals + departures at a known port. A single vessel call gets
-- one row; arrival_ts/departure_ts may be filled separately.
CREATE TABLE IF NOT EXISTS port_calls (
    id           SERIAL PRIMARY KEY,
    vessel_id    INTEGER NOT NULL REFERENCES vessels(id) ON DELETE CASCADE,
    port_code    VARCHAR(20),                    -- 'IS-ISA' for Ísafjörður
    port_name    VARCHAR(120),
    arrival_ts   TIMESTAMP,
    departure_ts TIMESTAMP,
    purpose      VARCHAR(120),
    source       VARCHAR(40)     NOT NULL,
    raw          JSONB,
    summary             TEXT,
    summary_embedding   vector(768),
    UNIQUE (vessel_id, arrival_ts, source)
);

CREATE INDEX IF NOT EXISTS idx_port_calls_vessel ON port_calls(vessel_id);
CREATE INDEX IF NOT EXISTS idx_port_calls_arrival ON port_calls(arrival_ts DESC);

-- ── ais_positions ──────────────────────────────────────────────
-- Time-series of AIS position reports. High write rate; partitioning
-- left for V2 (BIGSERIAL is enough for V1 volume in our bbox).
CREATE TABLE IF NOT EXISTS ais_positions (
    id          BIGSERIAL PRIMARY KEY,
    vessel_id   INTEGER REFERENCES vessels(id) ON DELETE SET NULL,
    mmsi        BIGINT,
    ts          TIMESTAMP    NOT NULL,
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    sog         REAL,                            -- speed over ground (kn)
    cog         REAL,                            -- course over ground (deg)
    heading     SMALLINT,
    nav_status  SMALLINT,
    raw         JSONB
);

CREATE INDEX IF NOT EXISTS idx_ais_pos_vessel_ts ON ais_positions(vessel_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_ais_pos_mmsi_ts ON ais_positions(mmsi, ts DESC);
CREATE INDEX IF NOT EXISTS idx_ais_pos_ts ON ais_positions(ts DESC);

-- ── weather_obs ────────────────────────────────────────────────
-- Wave / wind / sea state. Source = 'open-meteo' for V1.
CREATE TABLE IF NOT EXISTS weather_obs (
    id              BIGSERIAL PRIMARY KEY,
    station         VARCHAR(40)  NOT NULL,        -- 'open-meteo:isafjordur'
    ts              TIMESTAMP    NOT NULL,
    wind_dir        REAL,
    wind_ms         REAL,
    gust_ms         REAL,
    air_temp_c      REAL,
    sea_temp_c      REAL,
    wave_h_m        REAL,
    wave_period_s   REAL,
    wave_dir        REAL,
    swell_h_m       REAL,
    swell_period_s  REAL,
    current_v_ms    REAL,
    current_dir     REAL,
    raw             JSONB,
    UNIQUE (station, ts)
);

CREATE INDEX IF NOT EXISTS idx_weather_ts ON weather_obs(ts DESC);

-- ── traffic_events ─────────────────────────────────────────────
-- Joins YOLO detections (existing `detections` table) to candidate
-- vessels by AIS proximity / port-call schedule / manual override.
-- One detection can have multiple candidate matches; pick highest
-- score on read.
CREATE TABLE IF NOT EXISTS traffic_events (
    id                   SERIAL PRIMARY KEY,
    detection_id         INTEGER NOT NULL REFERENCES detections(id) ON DELETE CASCADE,
    candidate_vessel_id  INTEGER REFERENCES vessels(id) ON DELETE SET NULL,
    match_kind           VARCHAR(40),              -- 'ais_proximity' | 'schedule' | 'manual'
    match_score          REAL,
    summary              TEXT,
    summary_embedding    vector(768),
    created_at           TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_traffic_events_detection ON traffic_events(detection_id);
CREATE INDEX IF NOT EXISTS idx_traffic_events_vessel ON traffic_events(candidate_vessel_id);

-- ── ingestion_runs ─────────────────────────────────────────────
-- Audit log of every n8n / sidecar ingestion run. Used to debug
-- "why didn't yesterday's vessels appear" without grepping logs.
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id          SERIAL PRIMARY KEY,
    workflow    VARCHAR(80) NOT NULL,             -- 'open-meteo' | 'samgongustofa-yearly' | 'ais-ingest'
    started_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP,
    status      VARCHAR(20) NOT NULL,             -- 'running' | 'ok' | 'fail'
    rows_in     INTEGER,
    rows_out    INTEGER,
    notes       TEXT
);

CREATE INDEX IF NOT EXISTS idx_ingestion_workflow_started
    ON ingestion_runs(workflow, started_at DESC);

-- ── End of migration ───────────────────────────────────────────
-- Verify with:
--   \dt
--   SELECT extname, extversion FROM pg_extension WHERE extname='vector';

-- mbl.is 200mílur skipaskrá vessel photo (added 2026-05-12; populated by poc/scripts/scrape-mbl-photos.py)
ALTER TABLE vessels ADD COLUMN IF NOT EXISTS photo_url text;
ALTER TABLE vessels ADD COLUMN IF NOT EXISTS photo_caption text;
ALTER TABLE vessels ADD COLUMN IF NOT EXISTS photo_fetched_at timestamptz;
