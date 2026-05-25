// Graph schema init for hafnarvaktin (Neo4j 5).
// Run once after Neo4j first start:
//   docker -c user exec -i hafnarvaktin-graph cypher-shell -u neo4j -p $PW < db/graph-init/01-init.cypher

// ── Constraints ──────────────────────────────────────────────
CREATE CONSTRAINT vessel_id_unique IF NOT EXISTS
    FOR (v:Vessel) REQUIRE v.id IS UNIQUE;

CREATE CONSTRAINT vessel_imo_unique IF NOT EXISTS
    FOR (v:Vessel) REQUIRE v.imo IS UNIQUE;

CREATE CONSTRAINT vessel_mmsi_unique IF NOT EXISTS
    FOR (v:Vessel) REQUIRE v.mmsi IS UNIQUE;

CREATE CONSTRAINT port_code_unique IF NOT EXISTS
    FOR (p:Port) REQUIRE p.code IS UNIQUE;

CREATE CONSTRAINT camera_id_unique IF NOT EXISTS
    FOR (c:Camera) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT detection_id_unique IF NOT EXISTS
    FOR (d:Detection) REQUIRE d.id IS UNIQUE;

CREATE CONSTRAINT country_code_unique IF NOT EXISTS
    FOR (c:Country) REQUIRE c.code IS UNIQUE;

// ── Indexes (range, for filters) ─────────────────────────────
CREATE INDEX vessel_name_idx IF NOT EXISTS
    FOR (v:Vessel) ON (v.name_normalised);

CREATE INDEX detection_ts_idx IF NOT EXISTS
    FOR (d:Detection) ON (d.ts);

CREATE INDEX port_call_arrival_idx IF NOT EXISTS
    FOR (pc:PortCall) ON (pc.arrival_ts);

// ── Seed nodes ───────────────────────────────────────────────
// The two cameras and the local port. Edges to vessels are filled
// at ingest time.
MERGE (p:Port {code: 'IS-ISA'})
    ON CREATE SET p.name = 'Ísafjörður (Sundahöfn area)',
                  p.country = 'IS',
                  p.lat = 66.0750,
                  p.lon = -23.1306,
                  p.created_at = datetime();

MERGE (c1:Camera {id: 6})
    ON CREATE SET c1.name = 'Ísafjörður · Sundahöfn S',
                  c1.lat = 66.0747,
                  c1.lon = -23.1300,
                  c1.created_at = datetime();

MERGE (c2:Camera {id: 9})
    ON CREATE SET c2.name = 'Ísafjörður · Sundahöfn N',
                  c2.lat = 66.0760,
                  c2.lon = -23.1290,
                  c2.created_at = datetime();

MERGE (c1)-[:LOCATED_AT]->(p);
MERGE (c2)-[:LOCATED_AT]->(p);

MERGE (is:Country {code: 'IS'})
    ON CREATE SET is.name = 'Iceland';

MERGE (p)-[:IN]->(is);

// ── Done ─────────────────────────────────────────────────────
RETURN 'graph schema initialised' AS status;
