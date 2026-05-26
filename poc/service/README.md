# `service/` — YOLO inference service

`app.py` is a single-file Flask service. It opens the two Sundahöfn HLS streams,
runs the trained YOLO11m boat detector on each frame, and serves annotated
frames plus a detection event stream. One YOLO instance per camera, each in its
own capture thread, so the two cameras infer in parallel.

## HTTP routes

| route | returns |
|---|---|
| `GET /cameras` | JSON list of configured cameras |
| `GET /cameras/<id>/snapshot.jpg` | latest annotated frame (JPEG) |
| `GET /cameras/<id>/stream.mjpg` | live MJPEG stream |
| `GET /detections` | SSE stream of detection events |
| `GET /healthz` | readiness probe (ready once a frame is buffered) |

## What's inside `app.py`

| function | does |
|---|---|
| `load_cameras()` / `CameraConfig` | parse `CAMERAS_JSON` into typed camera configs |
| `capture_loop(cam, model)` | per-camera thread: read frame → infer → draw → buffer → broadcast |
| `_run_inference(frame, model, cam)` | YOLO predict, ROI filter, draw boxes, collect mining hits |
| `_draw_box(...)` | orange bbox + `boat NN%` label |
| `_draw_timestamp(...)` | burns a Snerpa-style watermark on camS (camN already has one) |
| `_box_passes_roi(...)` / `_load_roi_mask(...)` | per-camera water-only polygon filter |
| `_maybe_save_mining_frame(...)` | active learning: save uncertain raw frames for relabelling |
| `_subscribe` / `_unsubscribe` / `_broadcast` | in-process SSE fan-out to `/detections` clients |

## Config (env)

`MODEL_PATH`, `CONFIDENCE_THRESHOLD`, `IOU_THRESHOLD`, `INFER_IMGSZ`,
`PREVIEW_FPS`, `PORT` (default 8084) and `CAMERAS_JSON`, plus the optional
`MINING_*` and `ROI_MASK_CAM_*` knobs. Built into the `hafnarvaktin-inference`
container — see [`../README.md`](../README.md).
