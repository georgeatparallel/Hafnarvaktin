# `poc/backend` — Spring Boot API + dashboard

The Hafnarvaktin backend. Spring Boot 3.5 / Java 21. It sits between the Python
inference service and the three clients (web dashboard, RN app, MCP agent):
it proxies live camera frames, records boat detections to Postgres, and serves
the vessel "Fleet" lists. Package layout follows the feature, one package per
domain.

Run locally against the compose DB:

```bash
./mvnw spring-boot:run        # needs hafnarvaktin-db on localhost:5432
```

## Classes by package

### root — `is.fljotavik.backend`
| class | what it is |
|---|---|
| `FljotavikBackendApplication` | Spring Boot entry point. `@EnableScheduling` powers the detection flush. |

### `config`
| class | what it is |
|---|---|
| `OpenApiConfig` | Registers the OpenAPI/Swagger metadata served at `/v3/api-docs`. |

### `camera` — camera registry
| class | what it is |
|---|---|
| `Camera` | JPA entity for the `cameras` table (name, location, rtsp_url). |
| `CameraRepository` | `JpaRepository<Camera>`; used by the components that validate a camera id. |
| `CameraSeeder` | At startup, upserts camera rows from the `CAMERAS_JSON` env var and resyncs the id sequence, so detection persistence (FK to `cameras.id`) never fails. |

### `inference` — talk to the Python YOLO service
| class | what it is |
|---|---|
| `DetectionBox` | Record: one box, `{cls, conf, xyxy}` in pixels. |
| `DetectionEvent` | Record: one SSE frame payload, `{ts, camera_id, camera_code, model, boxes}`. |
| `InferenceEventBus` | In-process fan-out. The SSE client publishes; the persistence service subscribes. A throwing subscriber never stops the bus. |
| `InferenceSseClient` | Daemon thread that holds the inference `GET /detections` SSE stream open and republishes each event onto the bus. Exponential backoff on drop. |
| `SnapshotController` | `GET /api/v1/cameras/{id}/snapshot` (one JPEG) and `…/stream.mjpg` (live MJPEG), both proxied from the inference service so clients stay on the backend origin. |

### `detection` — persist detections
| class | what it is |
|---|---|
| `Detection` | JPA entity for `detections` (camera, timestamp, labels). |
| `DetectionLabel` | JPA entity for `detection_labels` — class + confidence + bbox per hit. |
| `DetectionPersistenceService` | Subscribes to the bus, collapses a run of same-class hits on one camera into a single row (debounce window), and writes the peak-confidence box. Flushed by a `@Scheduled` sweep. |
| `DetectionRepository` | `JpaRepository<Detection>`; persistence saves through it. |

### `label` — detection classes
| class | what it is |
|---|---|
| `Label` | JPA entity for `labels` (class name + description). |
| `LabelRepository` | `findByName`; persistence auto-creates a label row the first time the model emits a new class. |

### `vessels` — the Fleet tab
| class | what it is |
|---|---|
| `VesselsController` | `GET /api/v1/vessels/status` (in-port / at-sea, AIS enriched with the Samgöngustofa registry) and `/live` (raw cached AIS for the MCP). Live AIS from Datalastic, cached 60 s; falls back to a registry split when the key is missing. |

### `resources/static` — the web dashboard
`index.html` + `app.js` + `styles.css`: the public Sundahöfn page that crossfades
the two annotated MJPEG streams.

## Use-case flows

**1 · Live frame → dashboard / RN**
`inference` annotated frame → `SnapshotController` proxy →
`/stream.mjpg` (web dashboard `index.html`) and `/snapshot` (RN Harbour tab + MCP `live_snapshot`).

**2 · Detection ingest → Postgres**
`inference /detections` SSE → `InferenceSseClient` → `InferenceEventBus` →
`DetectionPersistenceService` (debounce + peak box) → `Detection` + `DetectionLabel` → `detections` table.
That table is then counted by the n8n `harbour_activity` workflow for the Chat agent's activity answers.

**3 · Fleet status → RN**
RN Fleet tab → `GET /api/v1/vessels/status` → `VesselsController` →
Datalastic AIS (cached) enriched against the `vessels` registry → in-port / at-sea lists.
The MCP reads the same cached snapshot via `/api/v1/vessels/live`.

**4 · Camera bootstrap**
Startup → `CameraSeeder` upserts `CAMERAS_JSON` → `cameras` table → FK target for flow 2.

## Config

All wiring is in `src/main/resources/application.properties` and overridden by
env vars in compose: DB connection, `fljotavik.inference.base-url`, the detection
debounce/flush timings, and the Datalastic key + harbour lat/lon.
