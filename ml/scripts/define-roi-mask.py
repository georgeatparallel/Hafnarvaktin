#!/usr/bin/env python3
"""Interactive ROI polygon picker for a camera's water area.

Run on a machine with a GUI. It fetches a fresh camera snapshot over HTTP
and opens it in matplotlib; left-click drops polygon vertices around the
water (clockwise), and right-click or Enter closes the polygon and prints
the ROI_MASK_CAM_<code> env line for poc/.env. Once that line is set and
the inference service restarts, detections whose bbox centre falls outside
the polygon are dropped (mining still captures them for re-training).

Usage:
    python3 define-roi-mask.py --camera S --backend http://atlas.local:8191
    python3 define-roi-mask.py --camera N
"""
import argparse
import json
import urllib.request

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np


# Hafnarvaktin: numeric DB id ↔ short directional code.
CODE_TO_ID = {"N": 9, "S": 6}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", choices=["N", "S"], required=True,
                    help="Camera directional code (N=Sundahöfn N, S=Sundahöfn S).")
    ap.add_argument("--backend", default="http://localhost:8191")
    args = ap.parse_args()

    code = args.camera
    cam_id = CODE_TO_ID[code]
    snap_url = f"{args.backend}/api/v1/cameras/{cam_id}/snapshot"
    print(f"fetching {snap_url}")
    with urllib.request.urlopen(snap_url, timeout=15) as resp:
        data = resp.read()
    out_path = f"/tmp/cam{code}-snap.jpg"
    with open(out_path, "wb") as f:
        f.write(data)
    print(f"saved snapshot → {out_path}")

    img = mpimg.imread(out_path)
    h, w = img.shape[:2]
    print(f"image: {w}×{h} px")

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.imshow(img)
    ax.set_title(
        f"cam{code} — left-click to add polygon vertices "
        f"(clockwise around the water).\n"
        "Right-click or press Enter to close + print the env var."
    )

    points: list[tuple[int, int]] = []
    line, = ax.plot([], [], color="cyan", linewidth=2, marker="o")

    def redraw():
        if points:
            xs = [p[0] for p in points] + [points[0][0]]
            ys = [p[1] for p in points] + [points[0][1]]
            line.set_data(xs, ys)
        else:
            line.set_data([], [])
        fig.canvas.draw_idle()

    def on_click(event):
        if event.inaxes != ax:
            return
        if event.button == 1:
            points.append((int(event.xdata), int(event.ydata)))
            redraw()
        elif event.button == 3:
            close_and_print()

    def close_and_print(event=None):
        if len(points) < 3:
            print("need at least 3 points")
            return
        env_line = f"ROI_MASK_CAM_{code}={json.dumps([list(p) for p in points])}"
        print()
        print("Add this line to poc/.env (replace any existing one for the camera):")
        print()
        print("  " + env_line)
        print()
        print("Then recreate the inference container:")
        print(f"  cd poc")
        print(f"  docker compose up -d --force-recreate --no-deps hafnarvaktin-inference")
        plt.close(fig)

    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", lambda e: close_and_print() if e.key == "enter" else None)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
