# Hafnarvaktin

Three-course EK exam project: ML (Machine Learning) + AI (Agents & Automations) + RN (React Native), all built around live monitoring of the remote harbour at Ísafjörður, Westfjords, Iceland.

```
hafnarvaktin/
├── ml/                       Machine Learning exam — YOLO11m fine-tuned (v5: P 0.897 / R 0.983 / mAP50 0.931)
├── ai/                       AI exam — NanoClaw + MCP + n8n + Neo4j RAG + Telegram
├── rn/                       React Native exam — Expo app with three tabs (Harbour · Fleet · Chat)
└── poc/                      Proof-of-concept — pre-restructure project; LIVE STACK runs from here
```

## Live stack (in `poc/`)

```bash
cd poc
docker -c user compose ps        # check containers
docker -c user compose logs -f   # follow logs
docker -c user compose down      # stop
docker -c user compose up -d     # start
```

5 containers:
- `hafnarvaktin-db` — Postgres 17 + pgvector, 2,239 vessels + 96 weather rows
- `hafnarvaktin-graph` — Neo4j 5 Community, 2,239 Vessel nodes + Port + Cameras + Country, vector index `vessel_desc_idx`
- `hafnarvaktin-inference` — Python YOLO11m (host port `:8184` → container `:8084`)
- `hafnarvaktin-backend` — Spring Boot REST API + web dashboard (host port `:8191`)
- `hafnarvaktin-mcp` — MCP server, 8 tools over SSE (host port `:7000`)

## ML

- `ml/notebooks/` — `hafnarvaktin.ipynb` (Colab training notebook, Tesla T4)
- `ml/models/` — `best.pt` (v5, ~40 MB) + base weights — git-ignored, see `ml/models/README.md`
- `ml/data/` — mining frames + Roboflow export (`workspace-2s9cs/hafnarvaktin`) — git-ignored
- `ml/scripts/` — `define-roi-mask.py` (ROI helper)
- `ml/bilag/` — appendix images for the report
- `ml/ML-Hafnarvaktin.docx` — the ML exam report

The inference + backend containers that serve this model live in `poc/` (the live stack), not under `ml/`.

Final model **v5** (active learning over 205 images, single-class boat): **Precision 0.897 · Recall 0.983 · mAP50 0.931**. The v3 baseline (100 images) was P 0.916 · R 0.907 · mAP50 0.893 — recall climbed sharply across the v3 → v4 → v5 rounds.

## AI

Mandatory components per the AI course brief:

| component | location |
|---|---|
| **MCP** | `ai/mcp-server/` — Python single-file with 8 tools |
| **n8n** | `ai/n8n-workflows/` — exported JSONs (workflows running on the n8n instance) |
| **Neo4j vector RAG** | `(:Vessel).description_embedding` queried via `db.index.vector.queryNodes` |
| **Neo4j graph RAG** | Cypher traversals over `(:Vessel)-[:OWNED_BY]->(:Owner)` and `(:Vessel)-[:VISITED]->(:Port)` etc. |

Agent platform: **NanoClaw**. UI: **Telegram bot**.

## RN

`rn/sundahofn-spotter/` — Expo app with three tabs:
- **Harbour** — both Sundahöfn cameras (N=9, S=6) with server-drawn YOLO boxes, polled every ~1.5 s
- **Fleet** — Samgöngustofa-backed vessel list split into *In port* / *At sea* (backend `/api/v1/vessels/status`)
- **Chat** — asks the harbour assistant; POSTs to the AI exam's n8n webhook (same agent as Telegram/Slack)

Same unified backend as the ML + AI tracks — three demo surfaces over one stack.
