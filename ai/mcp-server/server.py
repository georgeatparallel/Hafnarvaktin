#!/usr/bin/env python3
"""Hafnarvaktin MCP server.

Exposes harbour data as MCP tools for the NanoClaw agent. Mandatory
components per the AI exam brief: MCP, n8n, Neo4j vector RAG, Neo4j
graph RAG. Each tool below maps to one of those.

Tools:
  search_vessels       Neo4j vector RAG — semantic vessel search
  graph_neighbours     Neo4j graph RAG — relationship traversal
  harbour_activity     n8n workflow — date-range summary
  live_snapshot        poc/backend HTTP — fresh annotated frame
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

import base64

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format="%(asctime)s %(levelname)s mcp-server %(message)s")
log = logging.getLogger("hafnarvaktin-mcp")


# ── Config ─────────────────────────────────────────────────────────
NEO4J_URL = os.environ.get("NEO4J_URL", "bolt://hafnarvaktin-graph:7687")
neo4j_user, neo4j_pw = os.environ["NEO4J_AUTH"].split("/", 1)

ML_BACKEND = os.environ.get("ML_BACKEND_URL", "http://hafnarvaktin-backend:8080")
N8N_HARBOUR_ACTIVITY_WEBHOOK = os.environ.get(
    "N8N_HARBOUR_ACTIVITY_URL",
    "http://n8n-compose-n8n-1:5678/webhook/harbour-activity",
)

# The n8n webhook sits behind a CDN that rejects requests carrying a default
# client User-Agent, so send a browser-style User-Agent for the call.
N8N_HEADERS = {
    "User-Agent": os.environ.get(
        "HTTP_USER_AGENT",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    )
}

EMBED_MODEL = os.environ.get("EMBED_MODEL", "intfloat/multilingual-e5-base")

# Datalastic — live AIS for the harbour-watch tools below.
DATALASTIC_API = "https://api.datalastic.com/api/v0"
DATALASTIC_KEY = os.environ.get("DATALASTIC_API_KEY", "")
# Sundahöfn (Ísafjörður) — used as the reference centre for radius queries.
HARBOUR_LAT = float(os.environ.get("HARBOUR_LAT", "66.07"))
HARBOUR_LON = float(os.environ.get("HARBOUR_LON", "-23.13"))


# ── Globals (lazy-loaded so server startup is fast) ─────────────────
_neo: GraphDatabase | None = None
_embedder: SentenceTransformer | None = None


def neo() -> Any:
    global _neo
    if _neo is None:
        _neo = GraphDatabase.driver(NEO4J_URL, auth=(neo4j_user, neo4j_pw))
    return _neo


def embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        log.info("loading embedding model %s ...", EMBED_MODEL)
        _embedder = SentenceTransformer(EMBED_MODEL)
        log.info("embedding model loaded.")
    return _embedder


# ── Tools ───────────────────────────────────────────────────────────

server = Server("hafnarvaktin")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_vessels",
            description=(
                "Find vessels by free-text semantic query (Neo4j vector RAG). "
                "Useful for fuzzy questions like 'old wooden fishing boats from "
                "the Westfjords' or 'recent passenger boats with diesel engines'. "
                "Returns up to N matches with similarity scores."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Free-text search query"},
                    "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="graph_neighbours",
            description=(
                "Get a vessel's relationship neighbourhood (Neo4j graph RAG). "
                "Returns owners, port-calls, sister-vessels (same owner), recent "
                "detection events. Use when you have a specific vessel id (from "
                "search_vessels) and want context."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "vessel_id": {"type": "integer", "description": "Postgres vessel id"},
                    "depth": {"type": "integer", "default": 2, "minimum": 1, "maximum": 3},
                },
                "required": ["vessel_id"],
            },
        ),
        Tool(
            name="harbour_activity",
            description=(
                "Summarise harbour activity at Sundahöfn (Ísafjörður) over a "
                "date range. Calls an n8n workflow that aggregates camera "
                "detections, port-call events and weather observations. "
                "Returns a short markdown summary."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["start_date", "end_date"],
            },
        ),
        Tool(
            name="live_snapshot",
            description=(
                "Grab a fresh annotated frame from one of the harbour cameras. "
                "Pass either the directional code (\"N\" = Sundahöfn N, \"S\" = "
                "Sundahöfn S) via `camera` — preferred — or the legacy numeric "
                "id (9 = N, 6 = S) via `camera_id`. Returns a URL to the JPEG "
                "plus the latest detection events for that camera."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "camera":    {"type": "string", "enum": ["N", "S"],
                                  "description": "Camera directional code (preferred)."},
                    "camera_id": {"type": "integer", "enum": [6, 9],
                                  "description": "Legacy numeric camera id (9=N, 6=S)."},
                },
            },
        ),
        Tool(
            name="vessels_near_harbour",
            description=(
                "Live AIS — list vessels currently within `radius_km` of Sundahöfn "
                "(Ísafjörður) via Datalastic. Returns name, MMSI, vessel type, "
                "and last AIS position timestamp. ALWAYS use this tool first when "
                "the user asks 'what's at the harbour now' / 'what's nearby' / "
                "'who's at sea right now'. Class-B AIS (small boats / strandveiði "
                "scale) is included. Default radius 10 km — increase to 30–50 km "
                "for a wider view of the Westfjords."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "radius_km": {
                        "type": "integer",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Radius in km from Sundahöfn (default 10).",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Max vessels to return.",
                    },
                },
            },
        ),
        Tool(
            name="vessel_position",
            description=(
                "Live AIS — latest position for a single vessel by MMSI. Returns "
                "lat/lon, speed, course, destination and ETA. Use after "
                "`vessels_near_harbour` or `lookup_vessel_by_hull` once you have "
                "an MMSI to deep-dive on."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mmsi": {"type": "string", "description": "Maritime Mobile Service Identity (9 digits)."},
                },
                "required": ["mmsi"],
            },
        ),
        Tool(
            name="lookup_vessel_by_hull",
            description=(
                "Exact-match lookup by hull / registration number (Icelandic "
                "skipaskrárnúmer / registration_no). This is the canonical id "
                "used by Samgöngustofa, Fiskistofa and harbour systems — ALWAYS "
                "try this FIRST whenever the user mentions a boat number, hull "
                "marking, or any short numeric/alphanumeric id seen on a vessel. "
                "Returns the same shape as `search_vessels` plus the internal id "
                "so you can chain into `graph_neighbours`."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "hull_number": {
                        "type": "string",
                        "description": "Hull / registration number, e.g. '2609' or 'IS-2609'. Leading prefix is stripped.",
                    },
                },
                "required": ["hull_number"],
            },
        ),
        Tool(
            name="ping_graph",
            description="Sanity-check tool — confirms Neo4j reachable and returns vessel count.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    arguments = arguments or {}
    log.info("tool=%s args=%s", name, arguments)

    if name == "ping_graph":
        with neo().session() as s:
            n = s.run("MATCH (v:Vessel) RETURN count(v) AS n").single()["n"]
        return [TextContent(type="text", text=f"Graph reachable. {n} Vessel nodes.")]

    if name == "vessels_near_harbour":
        if not DATALASTIC_KEY:
            return [TextContent(type="text", text="Datalastic API key not configured.")]
        radius = int(arguments.get("radius_km", 10))
        limit = int(arguments.get("limit", 20))
        # Route through the Hafnarvaktin backend cached AIS snapshot rather
        # than calling Datalastic directly, so this tool and the RN app Fleet
        # tab see the SAME vessel list (one 60 s cached snapshot, default 10 km).
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    f"{ML_BACKEND}/api/v1/vessels/live",
                    params={"radius": radius},
                )
                resp.raise_for_status()
                d = resp.json()
            except httpx.HTTPError as e:
                return [TextContent(type="text", text=f"Live AIS lookup failed: {e}")]
        items = (d.get("data") or {}).get("vessels") or []
        if not items:
            return [TextContent(type="text", text=f"No AIS-broadcasting vessels within {radius} km of Sundahöfn right now.")]

        # Enrich AIS rows with Icelandic registration_no (hull / IS-callsign)
        # by case-insensitive name-match in Neo4j. One batched Cypher query
        # for the whole fleet — O(1) round-trip regardless of vessel count.
        # Foreign vessels (no Samgöngustofa registration) silently miss
        # the lookup and render without parentheses.
        names_upper = [str(v.get("name") or "").strip().upper() for v in items if v.get("name")]
        hulls_by_name: dict[str, str] = {}
        if names_upper:
            try:
                with neo().session() as s:
                    for r in s.run(
                        "MATCH (v:Vessel) WHERE toUpper(v.name) IN $names "
                        "RETURN toUpper(v.name) AS uname, v.registration_no AS hull",
                        names=names_upper,
                    ):
                        d2 = r.data()
                        if d2.get("hull"):
                            hulls_by_name[d2["uname"]] = str(d2["hull"])
            except Exception as e:  # noqa: BLE001 — graceful: AIS data still useful w/o hull
                print(f"[vessels_near_harbour] Neo4j enrich failed: {e}", flush=True)

        # Compact one-line-per-boat layout for narrow chat bubbles (Telegram/Slack).
        # Format: "Name (hull) · type · Xkn · HH:MM"  — hull omitted when no DB match.
        # MMSI is deliberately omitted; surface it via vessel_position(mmsi) only
        # when the user explicitly asks for the AIS identifier.
        shown = items[:limit]
        lines = [f"{len(items)} vessel(s) within {radius} km of Sundahöfn (live AIS):"]
        for v in shown:
            name = v.get("name") or "?"
            hull = hulls_by_name.get(name.strip().upper())
            name_field = f"{name} ({hull})" if hull else name
            kind = v.get("type_specific") or v.get("type") or "?"
            spd = v.get("speed")
            spd_s = f"{spd}kn" if spd is not None else "—"
            ts = v.get("last_position_UTC") or ""
            hhmm = ts[11:16] if len(ts) >= 16 and ts[10] == "T" else (ts or "?")
            lines.append(f"{name_field} · {kind} · {spd_s} · {hhmm}")
        if len(items) > limit:
            lines.append(f"(+{len(items) - limit} more)")
        return [TextContent(type="text", text="\n".join(lines))]

    if name == "vessel_position":
        if not DATALASTIC_KEY:
            return [TextContent(type="text", text="Datalastic API key not configured.")]
        mmsi = str(arguments["mmsi"]).strip()
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"{DATALASTIC_API}/vessel",
                    params={"api-key": DATALASTIC_KEY, "mmsi": mmsi},
                )
                resp.raise_for_status()
                d = resp.json()
            except httpx.HTTPError as e:
                return [TextContent(type="text", text=f"Datalastic call failed: {e}")]
        v = d.get("data")
        if not v:
            return [TextContent(type="text", text=f"No live AIS data for MMSI {mmsi}.")]
        return [TextContent(type="text", text=(
            f"**{v.get('name')}** (MMSI {v.get('mmsi')}, IMO {v.get('imo')}, flag {v.get('country_iso')})\n"
            f"  type: {v.get('type_specific') or v.get('type') or '?'}\n"
            f"  last AIS: {v.get('last_position_UTC')} at ({v.get('lat')}, {v.get('lon')})\n"
            f"  speed: {v.get('speed')} kn · course: {v.get('course')}° · heading: {v.get('heading')}°\n"
            f"  destination: {v.get('destination') or '—'}\n"
            f"  ETA: {v.get('eta_UTC') or '—'}"
        ))]

    if name == "lookup_vessel_by_hull":
        raw = str(arguments["hull_number"]).strip()
        # Strip common prefixes/suffixes the user might paste
        # ("IS-2609", "#2609", "2609.", etc.)
        import re
        m = re.search(r"\d+", raw)
        hull = m.group(0) if m else raw
        with neo().session() as s:
            row = s.run(
                """
                MATCH (v:Vessel) WHERE v.registration_no = $hull
                RETURN v.id AS id, v.name AS name, v.type AS type,
                       v.material AS material, v.length_m AS length_m,
                       v.manufactor_year AS year, v.home_port AS home_port,
                       v.reg_status AS reg_status, v.registration_no AS hull,
                       v.gt AS gt, v.engine_maker AS engine, v.manufacturer AS builder
                """,
                hull=hull,
            ).single()
        if not row:
            return [TextContent(
                type="text",
                text=(
                    f"No vessel with hull / registration_no '{hull}'. "
                    f"Try `search_vessels` with a name or descriptive query."
                ),
            )]
        d = row.data()
        # Compact 3-4 line layout, no markdown. Single vessel so a small
        # block is fine; same dot-separated style as the harbour list.
        lines = [
            f"{d['name']} · {d.get('type') or '?'} · {d.get('length_m') or '?'}m · GT {d.get('gt') or '?'}",
            f"{d.get('material') or '?'} · built {d.get('year') or '?'}"
            + (f" ({d['builder']})" if d.get('builder') else ""),
            f"home {d.get('home_port') or '?'} · {d.get('reg_status') or '?'} · hull {d['hull']}",
        ]
        if d.get('engine'):
            lines.append(f"engine {d['engine']}")
        return [TextContent(type="text", text="\n".join(lines))]

    if name == "search_vessels":
        q = arguments["query"]
        limit = int(arguments.get("limit", 5))
        emb = embedder().encode([f"query: {q}"]).tolist()[0]
        with neo().session() as s:
            results = s.run(
                """
                CALL db.index.vector.queryNodes('vessel_desc_idx', $limit, $emb)
                YIELD node, score
                RETURN node.id AS id, node.name AS name, node.type AS type,
                       node.material AS material, node.length_m AS length_m,
                       node.manufactor_year AS year, node.home_port AS home_port,
                       node.reg_status AS reg_status,
                       node.registration_no AS hull, score
                """,
                emb=emb, limit=limit,
            )
            rows = [r.data() for r in results]

        if not rows:
            return [TextContent(type="text", text=f"No vessels matched '{q}'.")]

        # Compact one-line-per-vessel layout. Cosine-similarity score is
        # dropped from the user-facing output — it's a debug field that
        # adds noise on a phone-sized chat bubble. Format puts the hull
        # number in parens right after the name so it's the same pattern
        # as the harbour list (`Name (hull) · ...`).
        lines = [f"Top {len(rows)} matches for '{q}':"]
        for r in rows:
            name_field = f"{r['name']} ({r['hull']})" if r.get('hull') else r['name']
            length_s = f"{r['length_m']}m" if r['length_m'] else "?m"
            year_s = str(r['year']) if r['year'] else "?"
            lines.append(
                f"{name_field} · {r['material'] or '?'} {r['type'] or '?'} · "
                f"{length_s} · built {year_s} · home {r['home_port'] or '?'} · "
                f"{r['reg_status'] or '?'}"
            )
        return [TextContent(type="text", text="\n".join(lines))]

    if name == "graph_neighbours":
        vid = int(arguments["vessel_id"])
        depth = int(arguments.get("depth", 2))
        with neo().session() as s:
            data = s.run(
                f"""
                MATCH (v:Vessel {{id: $id}})
                OPTIONAL MATCH (v)-[:OWNED_BY]->(o:Owner)
                OPTIONAL MATCH (v)-[visit:VISITED]->(p:Port)
                OPTIONAL MATCH (sister:Vessel)-[:OWNED_BY]->(o)
                  WHERE sister.id <> v.id
                RETURN v {{.id, .name, .type, .material, .length_m, .home_port}} AS vessel,
                       collect(DISTINCT o {{.name}}) AS owners,
                       collect(DISTINCT CASE WHEN visit IS NULL THEN null
                         ELSE {{arrival_ts: visit.arrival_ts, departure_ts: visit.departure_ts, port_code: p.code}} END)[..5] AS recent_calls,
                       collect(DISTINCT sister {{.id, .name, .type}})[..5] AS sister_vessels
                """,
                id=vid,
            ).single()

        if not data or not data["vessel"]:
            return [TextContent(type="text", text=f"No vessel with id {vid}.")]

        v = data["vessel"]
        out = [
            f"**{v['name']}** (id {v['id']}, {v['type'] or '?'}, "
            f"{v.get('material') or '?'}, {v.get('length_m') or '?'}m, "
            f"home {v.get('home_port') or '?'})"
        ]
        if data["owners"]:
            owners = [o["name"] for o in data["owners"] if o.get("name")]
            if owners:
                out.append(f"Owners: {', '.join(owners)}")
        if data["recent_calls"]:
            out.append("Recent port calls:")
            for c in data["recent_calls"]:
                if c.get("arrival_ts"):
                    out.append(
                        f"  - {c.get('arrival_ts')} → {c.get('departure_ts') or '(open)'} "
                        f"at {c.get('port_code') or '?'}"
                    )
        if data["sister_vessels"]:
            sisters = [f"{s['name']} ({s.get('type', '?')})" for s in data["sister_vessels"] if s.get("name")]
            if sisters:
                out.append(f"Sister vessels (same owner): {', '.join(sisters)}")
        return [TextContent(type="text", text="\n".join(out))]

    if name == "harbour_activity":
        start = arguments["start_date"]
        end = arguments["end_date"]
        async with httpx.AsyncClient(timeout=30.0, headers=N8N_HEADERS) as client:
            try:
                resp = await client.post(
                    N8N_HARBOUR_ACTIVITY_WEBHOOK,
                    json={"start_date": start, "end_date": end},
                )
                resp.raise_for_status()
                payload = resp.json() if resp.content else {}
            except Exception as e:
                # The n8n harbour-activity workflow runs on a different host and
                # may be unreachable or return nothing; degrade cleanly so the
                # agent can fall back to live AIS / detection data instead of
                # surfacing a stack trace.
                log.warning("harbour_activity n8n call failed: %s", e)
                return [TextContent(type="text", text=(
                    "harbour_activity summary is unavailable right now; "
                    "use live AIS (vessels_in_radius) and detection data instead."
                ))]
        text = payload.get("summary") or (
            "No harbour-activity summary was returned for that date range "
            "(the aggregation workflow returned no data)."
        )
        return [TextContent(type="text", text=text)]

    if name == "live_snapshot":
        # Accept either the directional code ("N"/"S") or the legacy numeric
        # id (9/6). Normalise to the numeric id used by the backend route.
        # Mapping: 9 ↔ N (Sundahöfn N), 6 ↔ S (Sundahöfn S).
        CODE_TO_ID = {"N": 9, "S": 6}
        ID_TO_CODE = {9: "N", 6: "S"}
        if "camera" in arguments and arguments["camera"]:
            code = str(arguments["camera"]).strip().upper()
            if code not in CODE_TO_ID:
                return [TextContent(type="text", text=f"Unknown camera code '{code}'. Use 'N' or 'S'.")]
            cam_id = CODE_TO_ID[code]
        elif "camera_id" in arguments and arguments["camera_id"] is not None:
            cam_id = int(arguments["camera_id"])
            code = ID_TO_CODE.get(cam_id, "?")
        else:
            return [TextContent(type="text", text="Provide either `camera` (\"N\"/\"S\") or `camera_id` (9/6).")]
        cam_label = {"N": "Sundahöfn N", "S": "Sundahöfn S"}.get(code, f"camera {cam_id}")
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(f"{ML_BACKEND}/api/v1/cameras/{cam_id}/snapshot")
                resp.raise_for_status()
            except httpx.HTTPError as e:
                return [TextContent(type="text", text=f"snapshot fetch failed: {e}")]
        img_b64 = base64.b64encode(resp.content).decode("ascii")
        # Return both a text caption and the JPEG itself so the (multimodal)
        # caller can SEE the frame and describe what's in it. The annotated
        # JPEG already includes the YOLO11m bounding boxes.
        return [
            TextContent(
                type="text",
                text=(
                    f"Live frame for {cam_label} (cam{code}, internal id {cam_id}). "
                    "Boxes shown are from the fine-tuned YOLO11m boat detector."
                ),
            ),
            ImageContent(type="image", data=img_b64, mimeType="image/jpeg"),
        ]

    return [TextContent(type="text", text=f"Unknown tool '{name}'.")]


async def main_stdio() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main_sse(host: str, port: int) -> None:
    """Serve MCP over HTTP on one port via two transports:

      /mcp   Streamable HTTP (stateless, JSON responses) — the current MCP
             HTTP transport. Each tool call is a self-contained POST/response,
             which stays robust across network intermediaries. Preferred.
      /sse   Legacy HTTP+SSE. Kept as a fallback for older clients.
    """
    import contextlib
    from mcp.server.sse import SseServerTransport
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.responses import Response
    from starlette.routing import Mount, Route
    import uvicorn

    # ── Legacy SSE transport ────────────────────────────────────────
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send,
        ) as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
        # Starlette's Route wrapper expects the endpoint to return an ASGI app
        # or Response; without this, Starlette tries to call None and crashes.
        return Response()

    # ── Streamable HTTP transport ───────────────────────────────────
    # Stateless + JSON: each request is self-contained (no session affinity,
    # no long-lived server-push stream), so the transport stays robust across
    # network intermediaries.
    session_manager = StreamableHTTPSessionManager(
        app=server,
        event_store=None,
        json_response=True,
        stateless=True,
    )

    async def handle_mcp(scope, receive, send):
        await session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        async with session_manager.run():
            yield

    app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
            Mount("/mcp", app=handle_mcp),
        ],
        lifespan=lifespan,
    )
    log.info("starting MCP HTTP server on %s:%d (streamable /mcp + legacy /sse)", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import asyncio
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport == "sse":
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_PORT", "7000"))
        main_sse(host, port)
    else:
        asyncio.run(main_stdio())
