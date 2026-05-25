#!/usr/bin/env python3
"""Mirror Postgres `vessels` to Neo4j as (:Vessel) nodes.

Idempotent — uses MERGE on `id`. Run after Postgres bulk-load. Re-run
when source rows change; embeddings + relationships are layered on top
in later steps.
"""
import os
import sys
import psycopg
from neo4j import GraphDatabase

PG_DSN = (
    f"host={os.environ.get('PG_HOST', '127.0.0.1')} "
    f"port={os.environ.get('PG_PORT', '5432')} "
    f"dbname={os.environ['POSTGRES_DB']} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)
NEO4J_URL = os.environ.get("NEO4J_URL", "bolt://127.0.0.1:7687")
neo_user, neo_pw = os.environ["NEO4J_AUTH"].split("/", 1)

BATCH = 500


def main() -> None:
    print(f"PG: {PG_DSN.split(' password=')[0]}", file=sys.stderr)
    print(f"Neo4j: {NEO4J_URL} as {neo_user}", file=sys.stderr)

    with psycopg.connect(PG_DSN) as pg:
        with pg.cursor() as cur:
            cur.execute(
                "SELECT id, mmsi, imo, name, name_normalised, "
                "registration_no, type, length_m, beam_m, depth_m, gt, "
                "manufactor_year, manufacturer, material, engine_maker, "
                "home_port, district_no, reg_status, "
                "gfw_vessel_id, gear_type, ais_last_seen, source "
                "FROM vessels "
                "WHERE source = 'samgongustofa' "
                "ORDER BY id"
            )
            rows = cur.fetchall()

    n = len(rows)
    print(f"Mirroring {n} vessels to Neo4j", file=sys.stderr)

    with GraphDatabase.driver(NEO4J_URL, auth=(neo_user, neo_pw)) as driver:
        with driver.session() as session:
            for i in range(0, n, BATCH):
                batch = rows[i: i + BATCH]
                params = [
                    {
                        "id": r[0],
                        "mmsi": r[1],
                        "imo": r[2],
                        "name": r[3],
                        "name_normalised": r[4],
                        "registration_no": r[5],
                        "type": r[6],
                        "length_m": r[7],
                        "beam_m": r[8],
                        "depth_m": r[9],
                        "gt": r[10],
                        "manufactor_year": r[11],
                        "manufacturer": r[12],
                        "material": r[13],
                        "engine_maker": r[14],
                        "home_port": r[15],
                        "district_no": r[16],
                        "reg_status": r[17],
                        "gfw_vessel_id": r[18],
                        "gear_type": r[19],
                        "ais_last_seen": r[20].isoformat() if r[20] else None,
                        "source": r[21],
                    }
                    for r in batch
                ]
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (v:Vessel {id: row.id})
                      ON CREATE SET v.created_at = datetime()
                    SET v.mmsi = row.mmsi,
                        v.imo = row.imo,
                        v.name = row.name,
                        v.name_normalised = row.name_normalised,
                        v.registration_no = row.registration_no,
                        v.type = row.type,
                        v.length_m = row.length_m,
                        v.beam_m = row.beam_m,
                        v.depth_m = row.depth_m,
                        v.gt = row.gt,
                        v.manufactor_year = row.manufactor_year,
                        v.manufacturer = row.manufacturer,
                        v.material = row.material,
                        v.engine_maker = row.engine_maker,
                        v.home_port = row.home_port,
                        v.district_no = row.district_no,
                        v.reg_status = row.reg_status,
                        v.gfw_vessel_id = row.gfw_vessel_id,
                        v.gear_type = row.gear_type,
                        v.ais_last_seen = row.ais_last_seen,
                        v.source = row.source,
                        v.updated_at = datetime()
                    """,
                    rows=params,
                )
                print(f"  {min(i + BATCH, n)}/{n}", file=sys.stderr)

    print("done.", file=sys.stderr)


if __name__ == "__main__":
    main()
