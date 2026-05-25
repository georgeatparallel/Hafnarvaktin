#!/usr/bin/env python3
"""Fetch GFW port-visit events for our resolved Iceland vessels and
filter to visits at Ísafjörður (lat 66.0–66.15, lon -23.20–-23.05).

For each vessel with a `gfw_vessel_id`, hit `/v3/events` with the
`public-global-port-visits-events:latest` dataset, paginate, and
upsert qualifying visits into `port_calls`.

We DON'T pre-fetch GFW's anchorages dataset to find Ísafjörður's id —
the lat/lon bounding box is simpler and gives us multiple anchorages
inside the harbour (which is realistic; Ísafjörður isn't a single
anchorage in GFW's grouping).

Usage:
    python3 gfw-fetch-port-visits.py [--lookback-days 365] [--rps 3]
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import psycopg

GFW_API = "https://gateway.api.globalfishingwatch.org/v3"
TOKEN = os.environ["GFW_API_TOKEN"]

# Ísafjörður port bbox — covers Sundahöfn area + the inner fjord docks.
LAT_MIN, LAT_MAX = 66.00, 66.15
LON_MIN, LON_MAX = -23.20, -23.05

PG_DSN = (
    f"host={os.environ.get('PG_HOST', '127.0.0.1')} "
    f"port={os.environ.get('PG_PORT', '5432')} "
    f"dbname={os.environ['POSTGRES_DB']} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)


def gfw_events_for_vessel(vessel_id: str, start_date: str, end_date: str,
                           limit: int = 50) -> list[dict]:
    out = []
    offset = 0
    while True:
        qs = urllib.parse.urlencode({
            "datasets[0]": "public-global-port-visits-events:latest",
            "vessels[0]": vessel_id,
            "start-date": start_date,
            "end-date": end_date,
            "limit": limit,
            "offset": offset,
        }, safe="[]:")  # keep ':' unencoded — GFW returns 403 on %3A
        req = urllib.request.Request(
            f"{GFW_API}/events?{qs}",
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Accept": "application/json",
                "User-Agent": "hafnarvaktin/1.0 (academic; alexanderornb@gmail.com)",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.load(resp)
        entries = payload.get("entries") or []
        out.extend(entries)
        next_offset = payload.get("nextOffset")
        if not next_offset or len(entries) < limit:
            break
        offset = next_offset
    return out


def in_isafjordur(ev: dict) -> bool:
    pos = ev.get("position") or {}
    lat = pos.get("lat")
    lon = pos.get("lon")
    if lat is None or lon is None:
        return False
    return (LAT_MIN <= lat <= LAT_MAX) and (LON_MIN <= lon <= LON_MAX)


def upsert_port_call(cur, our_vessel_id: int, ev: dict) -> None:
    pv = ev.get("port_visit") or {}
    cur.execute(
        """
        INSERT INTO port_calls
            (vessel_id, port_code, port_name, arrival_ts, departure_ts,
             purpose, source, raw)
        VALUES
            (%s, 'IS-ISA', 'Ísafjörður (Sundahöfn area)',
             %s::timestamp, %s::timestamp,
             %s, 'gfw', %s::jsonb)
        ON CONFLICT (vessel_id, arrival_ts, source) DO UPDATE SET
            departure_ts = EXCLUDED.departure_ts,
            raw          = EXCLUDED.raw
        """,
        (
            our_vessel_id,
            ev.get("start"),
            ev.get("end"),
            f"port_visit (confidence {pv.get('confidence')}, dur {pv.get('durationHrs')}h)",
            json.dumps(ev),
        ),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookback-days", type=int, default=365)
    ap.add_argument("--rps", type=float, default=3.0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    from datetime import datetime, timedelta, timezone
    end_date = datetime.now(timezone.utc).date().isoformat()
    start_date = (datetime.now(timezone.utc) - timedelta(days=args.lookback_days)).date().isoformat()

    with psycopg.connect(PG_DSN) as conn:
        sql = (
            "SELECT id, name, gfw_vessel_id FROM vessels "
            "WHERE gfw_vessel_id IS NOT NULL "
            "ORDER BY id"
        )
        if args.limit:
            sql += f" LIMIT {args.limit}"
        rows = conn.execute(sql).fetchall()

    n = len(rows)
    print(f"checking port visits for {n} vessels, {start_date} → {end_date}", file=sys.stderr)
    sleep_s = 1.0 / args.rps if args.rps > 0 else 0.0

    total_events = 0
    isafjordur_visits = 0
    errors = 0
    for i, (our_id, name, vessel_id) in enumerate(rows):
        try:
            events = gfw_events_for_vessel(vessel_id, start_date, end_date)
            total_events += len(events)
            local = [e for e in events if in_isafjordur(e)]
            if local:
                with psycopg.connect(PG_DSN) as conn:
                    cur = conn.cursor()
                    for ev in local:
                        upsert_port_call(cur, our_id, ev)
                    conn.commit()
                isafjordur_visits += len(local)
                print(f"  [{i+1}/{n}] {name}: {len(local)} Ísafjörður visit(s) of {len(events)} total", file=sys.stderr)
        except urllib.error.HTTPError as e:
            errors += 1
            print(f"  [{i+1}/{n}] HTTP {e.code} on {name} vid={vessel_id}", file=sys.stderr)
            if e.code == 429:
                time.sleep(30)
        except Exception as e:
            errors += 1
            print(f"  [{i+1}/{n}] ERR on {name}: {e}", file=sys.stderr)

        if i % 25 == 0 and i > 0:
            print(f"  progress {i}/{n}  events={total_events}  isafj={isafjordur_visits}  err={errors}", file=sys.stderr)
        time.sleep(sleep_s)

    print(f"done. events={total_events} isafj_visits={isafjordur_visits} errors={errors}", file=sys.stderr)


if __name__ == "__main__":
    main()
