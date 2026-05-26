# `poc/` — the live stack

This is where the running Hafnarvaktin stack actually lives. It started as the
pre-restructure proof-of-concept and stayed the deployment root, so all three
exam tracks (ML, AI, RN) talk to the containers defined here. Everything runs
under one `docker compose` on Helmut.

## In — what feeds the stack

- **Two camera streams** — Sundahöfn N + S (Ísafjörður harbour), HLS pulled by the inference service.
- **Vessel registry** — Samgöngustofa mirror (~2,239 boats) loaded into Postgres + Neo4j.
- **Live AIS** — Datalastic `vessel_inradius` around the harbour (10 km), cached 60 s.
- **Weather** — observations stored in Postgres, summarised by the agent.

## Has — the five containers

| container | image / build | host port | role |
|---|---|---|---|
| `hafnarvaktin-db` | pgvector/pgvector:pg17 | — | Postgres 17 + pgvector: cameras, detections, vessels, weather |
| `hafnarvaktin-inference` | `./service` (Python) | `8184` → 8084 | YOLO11m boat detector over the two streams |
| `hafnarvaktin-backend` | `./backend` (Spring Boot) | `8191` → 8080 | REST API + web dashboard (see `backend/README.md`) |
| `hafnarvaktin-graph` | neo4j:5-community | `7474`/`7687` | vessel/port graph + vector index for RAG |
| `hafnarvaktin-mcp` | `../ai/mcp-server` | `7000` | MCP tools exposed to the agent over SSE |

## Flows — how a frame and a question move through

```
cameras ──HLS──> inference ──annotated frames──> backend ──> web dashboard (MJPEG)
                     │                              │
                     │ detection SSE                └──snapshot──> RN "Harbour" tab
                     ▼
                  backend persists boat detections ──> Postgres `detections`
                                                            │
Datalastic AIS ──> backend /vessels ──> RN "Fleet" tab      │ counted by n8n
                                                            ▼
RN "Chat" / Telegram ──> n8n ──> MCP tools (graph RAG, AIS, harbour_activity) + Postgres
```

## Does

- Detects boats on the two harbour cameras in near-real-time (YOLO11m, v5 weights from `ml/`).
- Serves annotated snapshots / MJPEG streams and a Fleet list (in-port vs at-sea) over a REST API.
- Records detections to Postgres so the agent can report harbour activity over a date range.
- Exposes harbour tools (vessel search, graph neighbours, live snapshot, AIS, activity) to the agent via MCP.

## Out — who consumes it

- **Web dashboard** — `http://<host>:8191/` (the two live camera feeds).
- **RN app** (`rn/sundahofn-spotter`) — snapshots + Fleet status.
- **Agent** (NanoClaw via n8n) — answers in the RN Chat tab, on Telegram and on Slack.

## Run

```bash
cd poc
docker -c user compose up -d        # start
docker -c user compose ps           # status
docker -c user compose logs -f      # follow logs
docker -c user compose down         # stop
```

Secrets load from `./.env` (chmod 600). The DB seeds from `db/` on first init only.

## Layout

```
poc/
├── backend/            Spring Boot REST API + web dashboard (own README)
├── service/            Python YOLO inference service (app.py)
├── db/                 schema.sql, migrations, Neo4j init, camera seed
├── docs/               uiverse snippets used by the dashboard
└── docker-compose.yml  orchestration for the five containers above
```
