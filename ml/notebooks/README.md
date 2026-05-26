# `notebooks/` — Colab training notebook

`hafnarvaktin.ipynb` is the Colab notebook used to train the YOLO11m boat
detector on a Tesla T4.

## Before re-running in Colab

The committed notebook pulls **Roboflow dataset version 3**:

```python
dataset = project.version(3).download("yolov11")
```

The deployed model (`../models/best.pt`) is **v5**. To reproduce the deployed
weights, bump the version to '6'(v5) before running:

```python
dataset = project.version(6).download("yolov11")
```

The notebook's saved cell outputs are from the v3 round, so they don't match the
final v5 metrics. Screenshots from the actual v5 run are in
[`../bilag/colab-v5/`](../bilag/colab-v5/).

<img width="1476" height="1006" alt="roboflow-workspace-hafnarvaktin" src="https://github.com/user-attachments/assets/96c0e593-04cd-4b04-85e8-4e54029cbd3e" />
