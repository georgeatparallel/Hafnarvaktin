"""
app.py — Hafnarvaktin inference service.

Reads two HLS streams (Sundahöfn N + S), runs my trained boat detector
on every frame, and exposes:

    GET /cameras                       JSON list of cameras
    GET /cameras/<id>/snapshot.jpg     latest annotated frame
    GET /cameras/<id>/stream.mjpg      live MJPEG
    GET /detections                    SSE detection events
    GET /healthz                       health probe

Cameras are configured by `CAMERAS_JSON` env var:
    [{"id":9,"code":"N","name":"…","url":"https://…/playlist.m3u8"}, …]
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, jsonify
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO


# ── Config from env ─────────────────────────────────────────────
MODEL_PATH  = os.environ.get("MODEL_PATH", "/app/models/best.pt")
CONFIDENCE  = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.25"))
# NMS IoU threshold. Ultralytics default is 0.7 (only boxes overlapping
# >70% get suppressed) — too permissive for our case where v4 sometimes
# fires on bow/midship/stern of a single large boat with ~50% pairwise
# overlap. 0.45 is the standard production-grade value and suppresses
# those part-detections cleanly without merging genuinely-adjacent boats.
IOU         = float(os.environ.get("IOU_THRESHOLD", "0.45"))
PREVIEW_FPS = float(os.environ.get("PREVIEW_FPS", "10"))
INFER_IMGSZ = int(os.environ.get("INFER_IMGSZ", "1280"))
PORT        = int(os.environ.get("PORT", "8084"))

# ── Active-learning frame mining ────────────────────────────────
# When enabled, save the raw (un-annotated) frame to disk whenever a
# detection's confidence falls in the [LOW, HIGH] uncertainty band — these
# are the frames where the model is unsure (weak true positives + near-miss
# false positives). Labelling exactly these frames in Roboflow gives 5–10×
# more learning per labelled image than random sampling.
#
# The mining check considers raw model output BEFORE the confidence floor
# filter and BEFORE the ROI mask, so it captures the failure modes the
# live UI never shows.
MINING_ENABLED = os.environ.get("MINING_ENABLED", "false").lower() == "true"
MINING_DIR = Path(os.environ.get("MINING_DIR", "/tmp/hafnarvaktin-mining"))
MINING_CONF_LOW  = float(os.environ.get("MINING_CONF_LOW",  "0.20"))
MINING_CONF_HIGH = float(os.environ.get("MINING_CONF_HIGH", "0.55"))
MINING_MIN_INTERVAL_SEC = float(os.environ.get("MINING_MIN_INTERVAL_SEC", "30"))


# ── Per-camera ROI mask (out-of-bounds filter) ───────────────────
# Fixed cameras stare at the same scene every frame, so static rocks,
# houses, the harbour wall, and dock infrastructure can produce repeated
# false-positive detections. We define a polygon per camera that describes
# the VALID detection area (typically just the water). A detection's bbox
# CENTER must fall inside the polygon to be persisted.
#
# Mining (the active-learning frame harvest) still captures detections
# even when they fail the mask, so re-training can learn to suppress
# the failure modes properly.
#
# Polygon format: env var ROI_MASK_CAM_<code> = JSON list of [x, y] pixel
# coordinates in the source frame, where <code> is the camera's short
# directional code ("N" or "S"). Use scripts/define-roi-mask.py to draw
# a precise polygon over a snapshot.
_ROI_CACHE: dict[str, "np.ndarray | None"] = {}

def _load_roi_mask(code: str) -> "np.ndarray | None":
    raw = os.environ.get(f"ROI_MASK_CAM_{code}", "").strip()
    if not raw:
        return None
    try:
        pts = json.loads(raw)
        if not isinstance(pts, list) or len(pts) < 3:
            print(f"[roi] cam{code}: polygon needs ≥3 points, got {pts!r}", flush=True)
            return None
        return np.array(pts, dtype=np.int32)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"[roi] cam{code}: failed to parse ROI_MASK_CAM_{code}: {exc}", flush=True)
        return None


def _roi_mask(code: str) -> "np.ndarray | None":
    if code not in _ROI_CACHE:
        poly = _load_roi_mask(code)
        _ROI_CACHE[code] = poly
        if poly is not None:
            print(f"[roi] cam{code}: polygon loaded ({len(poly)} vertices)", flush=True)
    return _ROI_CACHE[code]


ROI_MASK_MODE = os.environ.get("ROI_MASK_MODE", "keep").lower()  # "keep" | "exclude"


def _box_passes_roi(code: str, x1: int, y1: int, x2: int, y2: int) -> bool:
    poly = _roi_mask(code)
    if poly is None:
        return True
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    inside = cv2.pointPolygonTest(poly, (cx, cy), False) >= 0
    # ROI_MASK_MODE=keep:    polygon = water (the area to KEEP). Pass when inside.
    # ROI_MASK_MODE=exclude: polygon = rocks/houses (the area to DROP). Pass when outside.
    if ROI_MASK_MODE == "exclude":
        return not inside
    return inside


BOX_COLOR = (0, 165, 255)  # orange-BGR for boats

# Force TCP transport — UDP reads time out on flaky wifi. Harmless for HLS.
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"


# ── Camera configuration ────────────────────────────────────────
@dataclass(frozen=True)
class CameraConfig:
    id: int      # numeric DB primary key
    code: str    # short directional code ("N" / "S") — used in logs, mining paths, ROI env vars
    name: str
    url: str


def load_cameras() -> list[CameraConfig]:
    raw = os.environ["CAMERAS_JSON"]
    cams: list[CameraConfig] = []
    for c in json.loads(raw):
        cams.append(CameraConfig(
            id=int(c["id"]),
            code=str(c["code"]).strip(),
            name=str(c["name"]),
            url=str(c["url"]),
        ))
    return cams


CAMERAS: list[CameraConfig] = load_cameras()
CAMERAS_BY_ID: dict[int, CameraConfig] = {c.id: c for c in CAMERAS}


# ── Per-camera latest-frame store ───────────────────────────────
_latest_jpeg: dict[int, bytes] = {}
_latest_lock = threading.Lock()


# ── Frame-mining throttle state ─────────────────────────────────
_mining_last_saved: dict[int, float] = {}
_mining_lock = threading.Lock()


# ── SSE subscriber fan-out (all cameras merged) ─────────────────
_subscribers: list[queue.Queue] = []
_subscribers_lock = threading.Lock()
_SUBSCRIBER_QUEUE_SIZE = 64


def _subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=_SUBSCRIBER_QUEUE_SIZE)
    with _subscribers_lock:
        _subscribers.append(q)
    return q


def _unsubscribe(q: queue.Queue) -> None:
    with _subscribers_lock:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass


def _broadcast(event: dict) -> None:
    payload = json.dumps(event, separators=(",", ":"))
    with _subscribers_lock:
        targets = list(_subscribers)
    for q in targets:
        try:
            q.put_nowait(payload)
        except queue.Full:
            pass


# ── Frame processing ────────────────────────────────────────────
def _draw_box(frame, x1, y1, x2, y2, label, confidence):
    cv2.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, 2)
    text = f"{label} {int(round(confidence * 100))}%"
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    cv2.rectangle(frame, (x1, y1 - th - baseline - 6), (x1 + tw + 8, y1), BOX_COLOR, -1)
    cv2.putText(
        frame, text, (x1 + 4, y1 - baseline - 2),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2,
    )


_OVERLAY_FONT_PATH = "/usr/local/lib/python3.11/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf"
_OVERLAY_FONT_SIZE = 18
try:
    _OVERLAY_FONT = ImageFont.truetype(_OVERLAY_FONT_PATH, _OVERLAY_FONT_SIZE)
except OSError:
    _OVERLAY_FONT = ImageFont.load_default()

# Larger regular-weight face for the Snerpa-style watermark mimic on camS.
_WATERMARK_FONT_SIZE = 26
try:
    _WATERMARK_FONT = ImageFont.truetype(_OVERLAY_FONT_PATH.replace("DejaVuSans-Bold", "DejaVuSans"), _WATERMARK_FONT_SIZE)
except OSError:
    try:
        _WATERMARK_FONT = ImageFont.truetype(_OVERLAY_FONT_PATH, _WATERMARK_FONT_SIZE)
    except OSError:
        _WATERMARK_FONT = ImageFont.load_default()


def _draw_timestamp(frame, cam: CameraConfig, frame_counter: int) -> None:
    """Watermark parity across the two cameras.

    camN's source already carries Snerpa's watermark (top-left: date/time +
    "Sundahofn"), so we leave it untouched. camS's source has none, so we burn
    a matching one there. No separate debug info-bar is drawn any more.
    Iceland is UTC year-round, so UTC == local — no tz math.
    """
    if cam.code == "N":
        return  # Snerpa already watermarks the north feed.

    now = datetime.now(timezone.utc)
    lines = [now.strftime("%d/%m/%Y %H:%M:%S"), "Sundahofn"]

    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img)

    x, y = 10, 6
    for line in lines:
        draw.text((x + 1, y + 1), line, font=_WATERMARK_FONT, fill=(0, 0, 0))   # shadow
        draw.text((x, y), line, font=_WATERMARK_FONT, fill=(255, 255, 255))     # white
        y += _WATERMARK_FONT_SIZE + 4

    frame[:] = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


# Each camera thread gets its own YOLO instance (loaded in __main__) so
# the two cameras run inference in parallel on different Pi 5 cores.
# A single shared instance would need a lock around .predict() because
# Ultralytics models aren't safe for concurrent calls.
def _run_inference(frame, model, cam: CameraConfig):
    # Raw confidences in the mining band — populated even for boxes that get
    # filtered out by the confidence floor or the ROI mask. Those near-misses
    # are the highest-value training frames.
    mining_hits: list[tuple[str, float]] = []
    boxes_out: list[dict] = []

    results = model(
        frame, conf=CONFIDENCE, iou=IOU, imgsz=INFER_IMGSZ, verbose=False
    )[0]
    for box in results.boxes:
        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
        label = results.names[int(box.cls)]
        conf = float(box.conf)
        if MINING_ENABLED and MINING_CONF_LOW <= conf <= MINING_CONF_HIGH:
            mining_hits.append((label, conf))
        if not _box_passes_roi(cam.code, x1, y1, x2, y2):
            continue
        _draw_box(frame, x1, y1, x2, y2, label, conf)
        boxes_out.append({"cls": label, "conf": conf, "xyxy": [x1, y1, x2, y2]})

    return frame, boxes_out, mining_hits


def _maybe_save_mining_frame(
    raw_frame, cam: CameraConfig, mining_hits: list[tuple[str, float]]
) -> None:
    """Persist the un-annotated frame for later labelling, throttled per cam."""
    if not mining_hits:
        return

    now = time.time()
    with _mining_lock:
        last = _mining_last_saved.get(cam.id, 0.0)
        if now - last < MINING_MIN_INTERVAL_SEC:
            return
        _mining_last_saved[cam.id] = now

    top_label, top_conf = max(mining_hits, key=lambda h: h[1])
    safe_label = "".join(c if c.isalnum() else "-" for c in top_label)

    cam_dir = MINING_DIR / f"cam{cam.code}"
    try:
        cam_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[mining] mkdir failed {cam_dir}: {e}", flush=True)
        return

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = cam_dir / f"{ts}_{safe_label}_{int(round(top_conf * 100)):02d}.jpg"
    try:
        cv2.imwrite(str(out_path), raw_frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
    except OSError as e:
        print(f"[mining] write failed {out_path}: {e}", flush=True)


def capture_loop(cam: CameraConfig, model):
    print(f"[cam{cam.code}] opening: {cam.name} — {cam.url}", flush=True)
    cap = cv2.VideoCapture(cam.url, cv2.CAP_FFMPEG)
    frame_interval = 1.0 / PREVIEW_FPS
    frame_counter = 0

    while True:
        loop_start = time.time()

        if not cap.isOpened():
            print(f"[cam{cam.code}] stream closed — reconnecting in 2s", flush=True)
            cap.release()
            time.sleep(2)
            cap = cv2.VideoCapture(cam.url, cv2.CAP_FFMPEG)
            continue

        ok, frame = cap.read()
        if not ok:
            print(f"[cam{cam.code}] frame read failed — reconnecting", flush=True)
            cap.release()
            cap = cv2.VideoCapture(cam.url, cv2.CAP_FFMPEG)
            continue

        # Snapshot a clean copy BEFORE inference draws boxes on top —
        # mining wants the un-annotated frame so it can be labelled.
        raw_frame = frame.copy() if MINING_ENABLED else None

        frame, boxes, mining_hits = _run_inference(frame, model, cam=cam)
        if MINING_ENABLED and raw_frame is not None and mining_hits:
            _maybe_save_mining_frame(raw_frame, cam, mining_hits)

        frame_counter += 1
        _draw_timestamp(frame, cam, frame_counter)
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if ok:
            with _latest_lock:
                _latest_jpeg[cam.id] = buf.tobytes()

        if boxes:
            _broadcast({
                "ts": datetime.now(timezone.utc).isoformat(),
                "camera_id": cam.id,
                "camera_code": cam.code,
                "camera_name": cam.name,
                "model": "boat",
                "boxes": boxes,
            })

        elapsed = time.time() - loop_start
        time.sleep(max(0.0, frame_interval - elapsed))


# ── HTTP server ─────────────────────────────────────────────────
app = Flask(__name__)


@app.route("/cameras")
def cameras_list():
    return jsonify([{"id": c.id, "code": c.code, "name": c.name} for c in CAMERAS])


def _snapshot_response(cam_id: int):
    with _latest_lock:
        frame = _latest_jpeg.get(cam_id)
    if frame is None:
        return Response(status=503)
    return Response(
        frame,
        mimetype="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


def _mjpeg_response(cam_id: int):
    boundary = b"frame"

    def gen():
        interval = 1.0 / PREVIEW_FPS
        last_sent: bytes | None = None
        while True:
            with _latest_lock:
                frame = _latest_jpeg.get(cam_id)
            if frame is not None and frame is not last_sent:
                yield (
                    b"--" + boundary + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                    + frame + b"\r\n"
                )
                last_sent = frame
            time.sleep(interval)

    return Response(
        gen(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "close",
        },
    )


@app.route("/cameras/<int:cam_id>/snapshot.jpg")
def cam_snapshot(cam_id: int):
    if cam_id not in CAMERAS_BY_ID:
        return Response(status=404)
    return _snapshot_response(cam_id)


@app.route("/cameras/<int:cam_id>/stream.mjpg")
def cam_stream(cam_id: int):
    if cam_id not in CAMERAS_BY_ID:
        return Response(status=404)
    return _mjpeg_response(cam_id)


@app.route("/detections")
def detections():
    def gen():
        q = _subscribe()
        yield "retry: 5000\n\n"
        try:
            while True:
                try:
                    payload = q.get(timeout=15.0)
                    yield f"data: {payload}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            _unsubscribe(q)

    return Response(
        gen(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            # Allow cross-origin SSE so the dashboard at :8191 (Spring Boot)
            # can subscribe directly to this stream from a browser without a
            # backend-side proxy. Public detection data, no auth needed.
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.route("/healthz")
def healthz():
    with _latest_lock:
        ready_ids = sorted(_latest_jpeg.keys())
    ready = len(ready_ids) > 0
    return ({
        "ready": ready,
        "cameras_ready": ready_ids,
        "cameras_configured": [c.id for c in CAMERAS],
    }, 200 if ready else 503)



if __name__ == "__main__":
    print(
        f"Starting {len(CAMERAS)} capture thread(s), "
        f"imgsz={INFER_IMGSZ}, conf={CONFIDENCE}, iou={IOU}",
        flush=True,
    )
    if MINING_ENABLED:
        print(
            f"Frame mining ENABLED → {MINING_DIR} "
            f"(band={MINING_CONF_LOW}-{MINING_CONF_HIGH}, "
            f"throttle={MINING_MIN_INTERVAL_SEC}s/cam)",
            flush=True,
        )
    else:
        print("Frame mining disabled (set MINING_ENABLED=true to harvest)", flush=True)
    # One YOLO instance per camera so each capture thread runs inference
    # on its own CPU core in parallel.
    for cam in CAMERAS:
        print(f"[cam{cam.code}] loading model: {MODEL_PATH}", flush=True)
        cam_model = YOLO(MODEL_PATH)
        t = threading.Thread(
            target=capture_loop,
            args=(cam, cam_model),
            daemon=True,
            name=f"capture-cam{cam.code}",
        )
        t.start()

    app.run(host="0.0.0.0", port=PORT, threaded=True)
