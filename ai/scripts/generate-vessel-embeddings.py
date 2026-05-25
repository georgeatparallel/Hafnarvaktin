#!/usr/bin/env python3
"""Generate vessel description embeddings + write to Neo4j.

For each (:Vessel), compose a natural-language description from its
attributes, embed with intfloat/multilingual-e5-base (768d, multilingual
incl. Icelandic, runs on CPU), and store on the node as
`description_embedding`. Backs the AI exam's Neo4j vector RAG component.

Description format (intentional — semantic phrasing wins over key-value):
  "<name> is a <length>m <material translated> <vessel type translated>
   built in <year> by <manufacturer> with a <engine> engine. Home port
   <home_port>. Currently <reg_status>."

The translation step (Eik → "wooden", Stál → "steel", FISKISKIP → "fishing
vessel") makes the embeddings answer English questions like "any old
wooden boats around" naturally without users having to type Icelandic.

Usage:
    python3 generate-vessel-embeddings.py [--limit N] [--dry-run]
"""
import argparse
import os
import sys
from typing import Iterable

# import lazily so the file can be examined without the dependency installed
def _imports():
    from sentence_transformers import SentenceTransformer
    from neo4j import GraphDatabase
    return SentenceTransformer, GraphDatabase


MATERIAL_EN = {
    "Eik": "wooden",
    "Stál": "steel",
    "Plast": "fibreglass",
    "Ál": "aluminium",
    "Lerki": "larch wood",
    "Fura": "pine wood",
    "Óþekkt": "of unknown construction",
}

TYPE_EN = {
    "FISKISKIP": "fishing vessel",
    "Skemmtibátur": "pleasure boat",
    "FARÞEGASKIP": "passenger vessel",
    "Seglskip": "sailing vessel",
    "Björgunarskip": "rescue vessel",
    "Skuttogari": "stern trawler",
    "Vinnuskip": "work vessel",
    "Lóðsskip": "pilot boat",
    "Hvalveiðiskip": "whaling vessel",
    "Farþegabátur": "passenger boat",
    "Frístundafiskiskip": "recreational fishing vessel",
}


def translate_type(t: str | None) -> str:
    if not t:
        return "vessel"
    # Strip the " -> SUBTYPE" suffix island.is sometimes adds
    base = t.split("->")[-1].strip()
    base = base.replace("FISKISKIP", "FISKISKIP")  # noop
    return TYPE_EN.get(base) or TYPE_EN.get(t) or t.lower()


def translate_material(m: str | None) -> str | None:
    if not m:
        return None
    return MATERIAL_EN.get(m, m.lower())


def compose_description(v: dict) -> str:
    parts = []
    parts.append(v["name"])
    if v.get("length_m"):
        parts.append(f"is a {v['length_m']}m")
    else:
        parts.append("is a")
    mat = translate_material(v.get("material"))
    if mat:
        parts.append(mat)
    parts.append(translate_type(v.get("type")))
    if v.get("manufactor_year"):
        parts.append(f"built in {v['manufactor_year']}")
    if v.get("manufacturer"):
        parts.append(f"by {v['manufacturer']}")
    if v.get("engine_maker"):
        parts.append(f"with a {v['engine_maker']} engine")
    parts[-1] = parts[-1] + "."
    if v.get("home_port"):
        parts.append(f"Home port: {v['home_port']}.")
    if v.get("district_no"):
        parts.append(f"District: {v['district_no']}.")
    if v.get("reg_status"):
        parts.append(f"Status: {v['reg_status']}.")
    if v.get("gt"):
        parts.append(f"{v['gt']} GT.")
    return " ".join(p for p in parts if p)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch", type=int, default=64)
    args = ap.parse_args()

    SentenceTransformer, GraphDatabase = _imports()

    NEO4J_URL = os.environ.get("NEO4J_URL", "bolt://127.0.0.1:7687")
    user, pw = os.environ["NEO4J_AUTH"].split("/", 1)

    print("loading multilingual-e5-base ...", file=sys.stderr)
    model = SentenceTransformer("intfloat/multilingual-e5-base")
    print("model loaded.", file=sys.stderr)

    with GraphDatabase.driver(NEO4J_URL, auth=(user, pw)) as driver:
        with driver.session() as session:
            cypher = (
                "MATCH (v:Vessel) WHERE v.description_embedding IS NULL "
                "RETURN v.id AS id, v.name AS name, v.type AS type, "
                "v.length_m AS length_m, v.gt AS gt, v.material AS material, "
                "v.manufactor_year AS manufactor_year, "
                "v.manufacturer AS manufacturer, v.engine_maker AS engine_maker, "
                "v.home_port AS home_port, v.district_no AS district_no, "
                "v.reg_status AS reg_status "
                "ORDER BY v.id"
            )
            if args.limit:
                cypher += f" LIMIT {args.limit}"

            result = session.run(cypher)
            rows = [r.data() for r in result]

        n = len(rows)
        print(f"embedding {n} vessels in batches of {args.batch}", file=sys.stderr)

        if args.dry_run and rows:
            print("sample description:")
            print(f"  {compose_description(rows[0])}")
            return

        descs = [compose_description(r) for r in rows]
        # multilingual-e5-base expects "passage:" prefix at index time
        prefixed = [f"passage: {d}" for d in descs]

        for start in range(0, n, args.batch):
            batch = rows[start:start + args.batch]
            batch_texts = prefixed[start:start + args.batch]
            embeddings = model.encode(batch_texts, show_progress_bar=False).tolist()

            with driver.session() as session:
                params = [
                    {"id": r["id"], "embedding": e, "description": descs[start + i]}
                    for i, (r, e) in enumerate(zip(batch, embeddings))
                ]
                session.run(
                    """
                    UNWIND $rows AS row
                    MATCH (v:Vessel {id: row.id})
                    SET v.description_embedding = row.embedding,
                        v.description = row.description
                    """,
                    rows=params,
                )

            print(f"  {min(start + args.batch, n)}/{n}", file=sys.stderr)

    print("done.", file=sys.stderr)


if __name__ == "__main__":
    main()
