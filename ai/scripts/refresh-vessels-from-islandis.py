#!/usr/bin/env python3
"""Refresh `vessels` rows from island.is shipRegistryShipSearch.

For every vessel with source='samgongustofa' (or already refreshed once
older than --max-age-days), call the public GraphQL endpoint with the
vessel's registration_no, take the matching ship, and overwrite stale
fields with current data. Insert one row per owner into `vessel_owners`.

Idempotent. Re-runs are incremental — last call timestamp tracked per row.

Usage:
    PG_HOST=hafnarvaktin-db python3 refresh-vessels-from-islandis.py
        [--limit 50] [--max-age-days 0] [--rps 10]
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

try:
    import psycopg
except ImportError:
    sys.stderr.write("psycopg missing. Install with: pip install 'psycopg[binary]'\n")
    sys.exit(1)

ENDPOINT = "https://island.is/api/graphql"
QUERY = """query shipRegistryShipSearch($input: ShipRegistryShipSearchInput!){
  shipRegistryShipSearch(input:$input){
    ships{
      shipName shipType regno region portOfRegistry regStatus
      grossTonnage length manufactionYear manufacturer opid
      owners { name nationalId sharePercentage }
    }
  }
}"""

PG_DSN = (
    f"host={os.environ.get('PG_HOST', '127.0.0.1')} "
    f"port={os.environ.get('PG_PORT', '5432')} "
    f"dbname={os.environ['POSTGRES_DB']} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)


def call_islandis(qs: str, timeout: float = 15.0) -> list[dict]:
    body = json.dumps({"variables": {"input": {"qs": qs}}, "query": QUERY}).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "hafnarvaktin-refresh/1.0 (academic; alexanderornb@gmail.com)",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.load(resp)
    return ((payload.get("data") or {}).get("shipRegistryShipSearch") or {}).get("ships") or []


def normalise(name: str | None) -> str | None:
    return name.lower() if name else None


def upsert_vessel(cur, our_id: int, ship: dict) -> None:
    cur.execute(
        """
        UPDATE vessels SET
            name              = COALESCE(%s, name),
            name_normalised   = COALESCE(%s, name_normalised),
            type              = COALESCE(%s, type),
            length_m          = COALESCE(%s, length_m),
            gt                = COALESCE(%s, gt),
            home_port         = COALESCE(%s, home_port),
            district_no       = COALESCE(%s, district_no),
            reg_status        = COALESCE(%s, reg_status),
            manufactor_year   = COALESCE(%s, manufactor_year),
            manufacturer      = COALESCE(%s, manufacturer),
            opid              = COALESCE(%s, opid),
            islandis_refreshed_at = NOW(),
            updated_at        = NOW()
        WHERE id = %s
        """,
        (
            ship.get("shipName"),
            normalise(ship.get("shipName")),
            ship.get("shipType"),
            ship.get("length"),
            ship.get("grossTonnage"),
            ship.get("portOfRegistry"),
            ship.get("region"),
            ship.get("regStatus"),
            int(ship["manufactionYear"]) if ship.get("manufactionYear") and str(ship["manufactionYear"]).isdigit() else None,
            ship.get("manufacturer"),
            ship.get("opid"),
            our_id,
        ),
    )


def upsert_owners(cur, vessel_id: int, owners: list[dict]) -> None:
    for o in owners or []:
        cur.execute(
            """
            INSERT INTO vessel_owners (vessel_id, name, national_id, share_percent, source, updated_at)
            VALUES (%s, %s, %s, %s, 'islandis', NOW())
            ON CONFLICT (vessel_id, name, source) DO UPDATE SET
                national_id   = EXCLUDED.national_id,
                share_percent = EXCLUDED.share_percent,
                updated_at    = NOW()
            """,
            (vessel_id, o.get("name"), o.get("nationalId"), o.get("sharePercentage")),
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-age-days", type=int, default=0,
                    help="re-refresh rows already refreshed more than N days ago (0=only never-refreshed)")
    ap.add_argument("--rps", type=float, default=10.0)
    args = ap.parse_args()

    sleep_s = 1.0 / args.rps if args.rps > 0 else 0.0

    where = (
        "(islandis_refreshed_at IS NULL OR islandis_refreshed_at < NOW() - INTERVAL '%d days')"
        % args.max_age_days
    )
    sql = (
        f"SELECT id, registration_no, name FROM vessels "
        f"WHERE source='samgongustofa' AND registration_no IS NOT NULL "
        f"AND {where} "
        f"ORDER BY id"
    )
    if args.limit:
        sql += f" LIMIT {args.limit}"

    with psycopg.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()

    n = len(rows)
    print(f"refreshing {n} vessels at {args.rps} req/s (~{n/args.rps:.0f}s)", file=sys.stderr)

    matched = unmatched = errors = 0
    for i, (our_id, regno, our_name) in enumerate(rows):
        try:
            ships = call_islandis(str(regno))
            ship = next((s for s in ships if str(s.get("regno")) == str(regno)), None)
            if not ship:
                unmatched += 1
                with psycopg.connect(PG_DSN) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE vessels SET reg_status = COALESCE(reg_status, 'not_found_islandis'), "
                            "islandis_refreshed_at = NOW() WHERE id = %s",
                            (our_id,),
                        )
                        conn.commit()
            else:
                matched += 1
                with psycopg.connect(PG_DSN) as conn:
                    with conn.cursor() as cur:
                        upsert_vessel(cur, our_id, ship)
                        upsert_owners(cur, our_id, ship.get("owners") or [])
                        conn.commit()
        except urllib.error.HTTPError as e:
            errors += 1
            print(f"  [{i+1}/{n}] HTTP {e.code} on regno={regno}: {e.reason}", file=sys.stderr)
            time.sleep(2.0)
        except Exception as e:
            errors += 1
            print(f"  [{i+1}/{n}] ERR on regno={regno}: {e}", file=sys.stderr)

        if i % 100 == 0 and i > 0:
            print(f"  {i}/{n}  matched={matched} unmatched={unmatched} errors={errors}", file=sys.stderr)
        time.sleep(sleep_s)

    print(f"done. matched={matched} unmatched={unmatched} errors={errors}", file=sys.stderr)


if __name__ == "__main__":
    main()
