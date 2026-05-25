#!/usr/bin/env python3
"""Lift material + engine_maker + depth from vessels.raw.lines[1] into columns.

The 2022 Skipaskra PDF has each vessel's record on two lines:
  line 1: registration_no, name, owner, address, district, year, build_country, builder
  line 2: vessel_type, material, engine_maker, L, GT, NT, L2, B, D, total, freeboard

Multi-word engine names (e.g. "Volvo Penta", "M. Blackstone") mean we can't
just `split()[2]`. Strategy: walk tokens of line 2, the FIRST token that parses
as a decimal-comma number is the start of the dimensions. Everything before
is text in this order: vessel_type, material, engine_maker (1+ words).

Known caveats:
- "Trefja-plast" wraps to a continuation line so parser captured only "plast" — kept as is for V1
- Some entries have non-standard structure (older vessels with engine "Gufuvél" / steam, etc)

Usage:
    PG_HOST=hafnarvaktin-db python3 extract-vessel-attributes.py [--limit N] [--dry-run]
"""
import argparse
import json
import os
import re
import sys

import psycopg

DECIMAL_RE = re.compile(r"^\d+,\d+$")

PG_DSN = (
    f"host={os.environ.get('PG_HOST', '127.0.0.1')} "
    f"port={os.environ.get('PG_PORT', '5432')} "
    f"dbname={os.environ['POSTGRES_DB']} "
    f"user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)


def to_float(tok: str) -> float | None:
    if not DECIMAL_RE.match(tok):
        return None
    try:
        return float(tok.replace(",", "."))
    except ValueError:
        return None


def parse_line2(line: str) -> dict:
    """Return {material, engine_maker, dims[]}. None values when unparseable."""
    out = {"material": None, "engine_maker": None, "dims": []}
    if not line or not line.strip():
        return out

    tokens = line.split()
    # Find first decimal token = start of dimensions
    first_decimal = None
    for i, tok in enumerate(tokens):
        if DECIMAL_RE.match(tok):
            first_decimal = i
            break

    if first_decimal is None or first_decimal < 2:
        # No dimensions or not enough text tokens — bail
        return out

    text_tokens = tokens[:first_decimal]
    # Position 0 = vessel_type (we already have this from island.is, skip)
    # Position 1 = material
    # Positions 2..end of text = engine_maker
    if len(text_tokens) >= 2:
        out["material"] = text_tokens[1]
    if len(text_tokens) >= 3:
        out["engine_maker"] = " ".join(text_tokens[2:])

    out["dims"] = [to_float(t) for t in tokens[first_decimal:] if to_float(t) is not None]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sql = (
        "SELECT id, name, raw FROM vessels "
        "WHERE source='samgongustofa' AND raw IS NOT NULL "
        "ORDER BY id"
    )
    if args.limit:
        sql += f" LIMIT {args.limit}"

    updated = 0
    skipped = 0
    samples = []

    with psycopg.connect(PG_DSN) as conn:
        rows = conn.execute(sql).fetchall()
        n = len(rows)
        print(f"processing {n} vessels", file=sys.stderr)

        for our_id, name, raw in rows:
            lines = (raw or {}).get("lines") or []
            if len(lines) < 2:
                skipped += 1
                continue

            parsed = parse_line2(lines[1])
            material = parsed["material"]
            engine = parsed["engine_maker"]
            dims = parsed["dims"]
            depth_m = dims[2] if len(dims) >= 3 else None

            if not material and not engine and depth_m is None:
                skipped += 1
                continue

            if len(samples) < 5:
                samples.append((name, material, engine, dims[:5]))

            if not args.dry_run:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE vessels SET "
                        "  material = COALESCE(%s, material), "
                        "  engine_maker = COALESCE(%s, engine_maker), "
                        "  depth_m = COALESCE(%s, depth_m), "
                        "  updated_at = NOW() "
                        "WHERE id = %s",
                        (material, engine, depth_m, our_id),
                    )
                    conn.commit()
            updated += 1

        print(f"updated={updated} skipped={skipped}", file=sys.stderr)
        print("sample:", file=sys.stderr)
        for s in samples:
            print(f"  {s}", file=sys.stderr)


if __name__ == "__main__":
    main()
