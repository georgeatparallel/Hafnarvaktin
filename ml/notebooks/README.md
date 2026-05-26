# `notebooks/` — Colab training notebook

`hafnarvaktin.ipynb` is the Colab notebook used to train the YOLO11m boat
detector on a Tesla T4.

## Before re-running in Colab

The committed notebook pulls **Roboflow dataset version 3**:

```python
dataset = project.version(3).download("yolov11")
```

The deployed model (`../models/best.pt`) is **v5**. To reproduce the deployed
weights, bump the version to 5 before running:

```python
dataset = project.version(5).download("yolov11")
```

The notebook's saved cell outputs are from the v3 round, so they don't match the
final v5 metrics. Screenshots from the actual v5 run are in
[`../bilag/colab-v5/`](../bilag/colab-v5/).
