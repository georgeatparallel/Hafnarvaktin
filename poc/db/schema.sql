-- schema.sql
-- Docker runs this automatically on first startup because it is mounted at
-- /docker-entrypoint-initdb.d/01-schema.sql (followed by 02-seed-camera.sh).
-- It only runs when the data volume is empty (i.e. first time ever).
-- Do NOT include CREATE DATABASE or CREATE USER — Docker handles that via
-- the POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD env vars.

-- ── TABLES ──────────────────────────────────────────────────────

CREATE TABLE cameras (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    location   VARCHAR(200),
    rtsp_url   TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE labels (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE detections (
    id                 SERIAL PRIMARY KEY,
    camera_id          INTEGER NOT NULL REFERENCES cameras(id),
    timestamp          TIMESTAMP NOT NULL DEFAULT NOW(),
    thumbnail_path     TEXT NOT NULL,
    processing_time_ms INTEGER
);

CREATE TABLE detection_labels (
    id           SERIAL PRIMARY KEY,
    detection_id INTEGER NOT NULL REFERENCES detections(id),
    label_id     INTEGER NOT NULL REFERENCES labels(id),
    confidence   REAL NOT NULL,
    bbox_x       REAL,
    bbox_y       REAL,
    bbox_width   REAL,
    bbox_height  REAL
);

-- Speeds up the API query "get latest detections"
CREATE INDEX idx_detections_timestamp ON detections(timestamp DESC);

-- Speeds up "get all detections for camera X"
CREATE INDEX idx_detections_camera ON detections(camera_id);

-- ── SEED DATA ────────────────────────────────────────────────────

-- Label names must exactly match what YOLO returns from model.names
-- Run: python3 -c "from ultralytics import YOLO; m=YOLO('best.pt'); print(m.names)"
-- to verify before first run
INSERT INTO labels (name, description) VALUES
    ('fox',      'Arctic fox — common in Hornstrandir nature reserve'),
    ('atv',      'All-terrain vehicle — used by neighbouring summerhouse owners'),
    ('airplane', 'Small aircraft — detected by fine-tuned model'),
    ('person',   'Human — detected by base COCO model'),
    ('bird',     'Bird — detected by base COCO model'),
    ('boat',     'Boat — detected by base COCO model');

-- Camera seed rows are inserted by seed-camera.sh (next file in
-- /docker-entrypoint-initdb.d), which reads RTSP_USER / RTSP_PASSWORD /
-- RTSP_HOST from the environment so credentials stay out of this file.
