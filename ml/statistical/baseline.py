"""Model A - robust z-score baseline (package Section 12.1).

Trained on NORMAL-workload windows only (label == 0). The anomaly score of a
window is the mean of its k largest absolute robust z-scores
(median / MAD), so a single deviating feature family is enough to raise it.
Phase-II models (Isolation Forest, autoencoder) are compared against this.

  python -m ml.statistical.baseline --train datasets/features/normal.csv \
         --test datasets/features/mixed.csv --quantile 0.995
"""
from __future__ import annotations
import argparse
import json

import numpy as np
import pandas as pd

from feature_engine.src.feature_selection import select_features
from feature_engine.src.windowing import feature_columns
from ml.evaluation.metrics import detection_metrics


class RobustZBaseline:
    def __init__(self, top_k: int = 3, quantile: float = 0.995):
        self.top_k, self.quantile = top_k, quantile

    def fit(self, df: pd.DataFrame, cols: list[str]) -> "RobustZBaseline":
        self.cols = cols
        X = df[cols].to_numpy(float)
        self.med = np.median(X, axis=0)
        mad = np.median(np.abs(X - self.med), axis=0) * 1.4826
        std = X.std(axis=0)
        # floor: MAD of a mostly-constant feature is 0 -> use std, then a tiny epsilon
        self.scale = np.where(mad > 1e-9, mad, np.where(std > 1e-9, std, 1.0))
        self.threshold = float(np.quantile(self.score(df), self.quantile))
        return self

    def explain(self, df: pd.DataFrame, n: int = 3) -> list[list[str]]:
        Z = np.abs((df[self.cols].to_numpy(float) - self.med) / self.scale)
        return [[self.cols[j] for j in np.argsort(-row)[:n]] for row in Z]

    def score(self, df: pd.DataFrame) -> np.ndarray:
        Z = np.abs((df[self.cols].to_numpy(float) - self.med) / self.scale)
        k = min(self.top_k, Z.shape[1])
        return np.sort(Z, axis=1)[:, -k:].mean(axis=1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", nargs="+", required=True)
    ap.add_argument("--test", nargs="+", required=True)
    ap.add_argument("--quantile", type=float, default=0.995)
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--out-json")
    a = ap.parse_args(argv)

    tr = pd.concat([pd.read_csv(p) for p in a.train], ignore_index=True)
    te = pd.concat([pd.read_csv(p) for p in a.test], ignore_index=True)
    tr = tr[tr["label"] == 0]
    te = te[te["label"].isin([0, 1])].copy()
    cols, dropped = select_features(tr, feature_columns(tr))
    m = RobustZBaseline(a.top_k, a.quantile).fit(tr, cols)
    te["score"] = m.score(te)
    res = detection_metrics(te["label"], te["score"], m.threshold)
    res.update(threshold=m.threshold, n_train=len(tr), n_test=len(te), n_features=len(cols))
    per = {}
    for sc, g in te[te["label"] == 1].groupby("scenario"):
        per[sc] = {"windows": int(len(g)), "recall": float((g["score"] >= m.threshold).mean())}
    res["per_scenario_recall"] = per
    print(json.dumps(res, indent=2))
    if a.out_json:
        open(a.out_json, "w").write(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
