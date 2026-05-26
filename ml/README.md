# `ml/` — Machine Learning exam track

## Layout

```
ml/
├── notebooks/              `hafnarvaktin.ipynb` — Colab training notebook (Tesla T4)
├── models/                 `best.pt` (v5) + base weights — git-ignored, bind-mounted into the inference container (see models/README.md)
├── data/                   training data — mining frames + Roboflow export (git-ignored)
├── scripts/                `define-roi-mask.py` — ROI helper
├── bilag/                  appendix images for the report
├── ML-Hafnarvaktin.docx    the ML exam report
└── exam-requirments.md     the ML course brief
```

The YOLO inference container (`poc/service/`) and the Spring Boot backend (`poc/backend/`) that serve this model live in `poc/` — that is the live stack and they live there with rest of Hafnarvaktin's 'backend' code. `ml/` holds the training-side artifacts and the report.

## Final training metrics (yolo11m, single-class boat)

Active learning over three rounds — v3 (100 imgs) → v4 (145) → v5 (205). The deployed model is **v5**:

| metric | v3 baseline | v5 (deployed) |
|---|---|---|
| Precision | 0.916 | 0.897 |
| Recall | 0.907 | 0.983 |
| mAP50 | 0.893 | 0.931 |

Recall climbed sharply (0.907 → 0.983) as each round added harder scenes. Dataset: Roboflow `workspace-2s9cs/hafnarvaktin` (80 train / 10 val / 10 test, single class). The full training journey and per-hyperparameter rationale are written up in the ML exam report.
