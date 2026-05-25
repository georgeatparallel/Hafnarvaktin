#!/usr/bin/env python3
"""Resolve our vessels[] rows to GFW vesselId via callsign / name.

For each Iceland-flagged vessel in our DB that has a callsign or name,
search GFW's vessel registry and store the matching vesselId + ssvid
(MMSI) + gear + last-AIS-seen on the vessel row.

Strategy:
- Prefer callsign (TFNQ etc.) when island.is has provided one — it's a
  unique identifier across registries.
- Fall back to name search, then filter by flag=ISL and prefer the
  most recently transmitting match.
- Skip vessels marked reg_status='Afmáð' (de-registered) — they won't
  have current AIS anyway.

Idempotent — uses gfw_resolved_at to avoid re-resolving.

Usage:
    python3 gfw-resolve-vessels.py [--limit N] [--rps 5] [--max-age-days 7]
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

PG_DSN = (
    f"host={os.environ.get('PG_HOST', '127.0.0.1')} "
    f"port={os.environ.get('PG_PORT', '5432')} "
    f"dbname={os.environ['POSTGRES_DB']} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)


def gfw_search(query: str, limit: int = 20) -> list[dict]:
    qs = urllib.parse.urlencode({
        "query": query,
        "datasets[0]": "public-global-vessel-identity:latest",
        "limit": limit,
    }, safe="[]:")  # keep ':' unencoded — GFW returns 403 on %3A
    req = urllib.request.Request(
        f"{GFW_API}/vessels/search?{qs}",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/json",
            "User-Agent": "hafnarvaktin/1.0 (academic; alexanderornb@gmail.com)",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp).get("entries", []) or []


def pick_iceland_match(entries: list[dict], hint_callsign: str | None,
                       hint_name: str | None) -> dict | None:
    """From entries, pick the best Icelandic active vessel."""
    candidates = []
    for e in entries:
        # registryInfo can be empty when pure-AIS vessel
        regs = e.get("registryInfo") or []
        for ri in regs:
            if ri.get("flag") != "ISL":
                continue
            score = 0
            if hint_callsign and ri.get("callsign") == hint_callsign:
                score += 100
            if hint_name and ri.get("shipname", "").upper() == hint_name.upper():
                score += 50
            tx_to = ri.get("transmissionDateTo") or ""
            if tx_to >= "2024":
                score += 20
            elif tx_to >= "2020":
                score += 5
            csi = e.get("combinedSourcesInfo") or [{}]
            vid = csi[0].get("vesselId") if csi else None
            gears = []
            for g in (csi[0].get("geartypes") or []) if csi else []:
                if g.get("name") and g["name"] != "NA":
                    gears.append(g["name"])
            candidates.append({
                "score": score,
                "vesselId": vid,
                "ssvid": ri.get("ssvid"),
                "callsign": ri.get("callsign"),
                "shipname": ri.get("shipname"),
                "gear": gears[0] if gears else None,
                "tx_to": tx_to,
            })
    if not candidates:
        return None
    candidates.sort(key=lambda c: c["score"], reverse=True)
    if candidates[0]["score"] <= 0:
        return None
    return candidates[0]


def resolve_one(call_sign: str | None, name: str | None) -> dict | None:
    if call_sign:
        try:
            entries = gfw_search(call_sign)
            match = pick_iceland_match(entries, call_sign, name)
            if match and match["score"] >= 100:  # callsign matched
                return match
        except urllib.error.HTTPError:
            pass

    if name:
        try:
            entries = gfw_search(name)
            return pick_iceland_match(entries, call_sign, name)
        except urllib.error.HTTPError:
            return None
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--rps", type=float, default=5.0)
    ap.add_argument("--max-age-days", type=int, default=7)
    args = ap.parse_args()
    sleep_s = 1.0 / args.rps if args.rps > 0 else 0.0

    where = (
        "(gfw_resolved_at IS NULL OR gfw_resolved_at < NOW() - INTERVAL '%d days')"
        % args.max_age_days
    )
    sql = (
        "SELECT id, name, call_sign FROM vessels "
        "WHERE source='samgongustofa' "
        "  AND (reg_status IS NULL OR reg_status NOT IN ('Afmáð', 'not_found_islandis')) "
        "  AND (call_sign IS NOT NULL OR name IS NOT NULL) "
        f" AND {where} "
        "ORDER BY id"
    )
    if args.limit:
        sql += f" LIMIT {args.limit}"

    with psycopg.connect(PG_DSN) as conn:
        rows = conn.execute(sql).fetchall()

    n = len(rows)
    print(f"resolving {n} vessels @ {args.rps} rps", file=sys.stderr)

    resolved = unresolved = errors = 0
    for i, (our_id, name, callsign) in enumerate(rows):
        try:
            match = resolve_one(callsign, name)
            with psycopg.connect(PG_DSN) as conn:
                cur = conn.cursor()
                if match and match.get("vesselId"):
                    # Update everything except mmsi (which has a unique constraint)
                    cur.execute(
                        "UPDATE vessels SET "
                        "  gfw_vessel_id = %s, "
                        "  gear_type = COALESCE(%s, gear_type), "
                        "  ais_last_seen = COALESCE(%s::timestamp, ais_last_seen), "
                        "  gfw_resolved_at = NOW() "
                        "WHERE id = %s",
                        (
                            match["vesselId"],
                            match.get("gear"),
                            (match.get("tx_to") or None),
                            our_id,
                        ),
                    )
                    # Try to set mmsi — skip if another vessel already has that mmsi
                    mmsi_str = match.get("ssvid")
                    if mmsi_str and mmsi_str.isdigit():
                        cur.execute(
                            "UPDATE vessels SET mmsi = %s "
                            "WHERE id = %s AND (mmsi IS NULL OR mmsi = %s) "
                            "  AND NOT EXISTS (SELECT 1 FROM vessels WHERE mmsi = %s AND id <> %s)",
                            (mmsi_str, our_id, mmsi_str, mmsi_str, our_id),
                        )
                    resolved += 1
                else:
                    cur.execute(
                        "UPDATE vessels SET gfw_resolved_at = NOW() WHERE id = %s",
                        (our_id,),
                    )
                    unresolved += 1
                conn.commit()
        except urllib.error.HTTPError as e:
            errors += 1
            print(f"  [{i+1}/{n}] HTTP {e.code} on id={our_id} cs={callsign} name={name}", file=sys.stderr)
            if e.code == 429:
                time.sleep(30)
            else:
                time.sleep(2)
        except Exception as e:
            errors += 1
            print(f"  [{i+1}/{n}] ERR on id={our_id}: {e}", file=sys.stderr)

        if i % 50 == 0 and i > 0:
            print(f"  {i}/{n}  resolved={resolved} unresolved={unresolved} errors={errors}", file=sys.stderr)
        time.sleep(sleep_s)

    print(f"done. resolved={resolved} unresolved={unresolved} errors={errors}", file=sys.stderr)


if __name__ == "__main__":
    main()
