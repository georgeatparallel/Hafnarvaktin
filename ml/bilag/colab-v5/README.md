# colab-v5 — training screenshots

Screenshots from the final **v5** Colab training run (yolo11m, single-class
boat, 205 images, Tesla T4) — the run that produced the deployed `best.pt`
(Precision 0.897 · Recall 0.983 · mAP50 0.931).

The **v4** round screenshots were lost, so the appendix keeps only the v3
baseline (`../colab-v3/`) and this final v5 run.

## Walkthrough

The run continues training from the v4 weights pulled off the Helmut server,
so v5 is one more active-learning round on top of v4 rather than a fresh start.

<table>
<tr>
<td align="center" width="33%"><b>1 · Setup</b><br><sub>install Ultralytics + Roboflow, pull the forked <code>hafnarvaktin</code> dataset (YOLO11 format)</sub><br><img src="ml-exam-retrained-1.png" width="270"></td>
<td align="center" width="33%"><b>2 · Split check</b><br><sub>train 164 / valid 21 / test 20 images · one class: <code>boat</code></sub><br><img src="ml-exam-retrained-2.png" width="270"></td>
<td align="center" width="33%"><b>3 · Label reprojection</b><br><sub>code that draws the YOLO ground-truth labels back as pixel boxes</sub><br><img src="ml-exam-retrained-3.png" width="270"></td>
</tr>
<tr>
<td align="center" width="33%"><b>4 · Ground-truth frames</b><br><sub>sample Sundahöfn N/S training frames with labelled boxes</sub><br><img src="ml-exam-retrained-4.png" width="270"></td>
<td align="center" width="33%"><b>5 · Resume + train</b><br><sub>wget v4 <code>best.pt</code> from Helmut → train yolo11m, 80 epochs, imgsz 1280, batch 4, patience 20</sub><br><img src="ml-exam-retrained-5.png" width="270"></td>
<td align="center" width="33%"><b>6 · Test evaluation</b><br><sub><code>val(split='test', conf=0.10)</code> → P 0.897 · R 0.983 · mAP50 0.931</sub><br><img src="ml-exam-retrained-6.png" width="270"></td>
</tr>
<tr>
<td align="center" width="33%"><b>7 · Export + confusion matrix</b><br><sub>save the v5 <code>best.pt</code> (40.7 MB) · normalized boat-vs-background matrix</sub><br><img src="ml-exam-retrained-7.png" width="270"></td>
<td align="center" width="33%"><b>8 · Training curves</b><br><sub>box / cls / dfl loss + precision / recall / mAP50 / mAP50-95</sub><br><img src="ml-exam-retrained-8.png" width="270"></td>
<td align="center" width="33%"><b>9 · Predictions</b><br><sub>the trained model on unseen test frames (predicted boxes)</sub><br><img src="ml-exam-retrained-9.png" width="270"></td>
</tr>
</table>
