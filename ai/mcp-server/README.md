# Hafnarvaktin MCP server

Single-file MCP server exposing harbour data as tools to the NanoClaw agent.

Mandatory components per the AI exam brief:

| component | tool that uses it |
|---|---|
| MCP | This server itself |
| n8n | `harbour_activity` (calls n8n webhook) |
| Neo4j vector RAG | `search_vessels` (uses `vessel_desc_idx`) |
| Neo4j graph RAG | `graph_neighbours` (Cypher traversal) |

Plus five more tools: `vessels_near_harbour` and `vessel_position` (live AIS via Datalastic), `lookup_vessel_by_hull` (exact registry lookup by skipaskrárnúmer), `live_snapshot` (fresh annotated camera frame), and `ping_graph` (sanity check) — **8 tools total**.

## Local run (after embeddings are populated)

```bash
docker -c user build -t hafnarvaktin-mcp .
docker -c user run --rm -i \
  --network hafnarvaktin_hafnarvaktin-net \
  -e NEO4J_AUTH="$(grep ^NEO4J_AUTH ../../poc/.env | cut -d= -f2-)" \
  hafnarvaktin-mcp
```

Communicates over stdio. NanoClaw / agent client connects via stdin/stdout.

## Tool quick reference

```
ping_graph()                          → "Graph reachable. 2239 Vessel nodes."
search_vessels("old wooden boats")    → top 5 vessels by semantic similarity
lookup_vessel_by_hull("2609")         → exact registry match by skipaskrárnúmer
graph_neighbours(vessel_id, depth=2)  → owner, port-calls, sister-vessels
vessels_near_harbour(radius_km=10)    → live AIS list within radius (Datalastic)
vessel_position("251234000")          → live AIS position/speed/course for one MMSI
harbour_activity("2026-04-01", "2026-04-30") → markdown summary from n8n
live_snapshot(camera="S")             → URL to fresh annotated frame from the backend
                                        (also accepts legacy camera_id=6/9)
```

## Where this fits

- `ai/db/neo4j-init/02-vector-index.cypher` — defines the index this server reads
- `ai/scripts/generate-vessel-embeddings.py` — one-shot job that fills the index
- `ai/n8n-workflows/` — exported workflow JSONs called by `harbour_activity`
- `poc/backend/` — Spring Boot REST API called by `live_snapshot`
