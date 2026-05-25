# Model weights

The deployed **v5** checkpoint `best.pt` (~40 MB) is committed here so the
inference container can run straight from a clone. The other checkpoints (base
`yolo11n.pt`, prior-round and training-run weights) stay out of git via
`.gitignore` to keep history small.

## Files

| File | Size | In git | Purpose |
|---|---|---|---|
| `best.pt` | ~40 MB | yes | Active YOLO11m fine-tune (v5), bind-mounted into the `hafnarvaktin-inference` container |
| `hafnarvaktin-yolo11m-best-v5.pt` | ~40 MB | no | v5 training-run checkpoint (source of the deployed `best.pt`) |
| `yolo11n.pt` | ~5 MB | no | Ultralytics YOLO11n base model |

## How to obtain the excluded weights

- Train in the Colab notebook `ml/notebooks/hafnarvaktin.ipynb` against the
  Roboflow dataset, then download the run's `best.pt`.
- Or request the binary weights directly (academic supervisor).
