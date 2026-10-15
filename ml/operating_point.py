#!/usr/bin/env python3
"""Choose each model's operating point (the quantile q that sets T1) WITHOUT peeking at the final test data.

Protocol: the held-out runs are split into VALIDATION (first half) and TEST (second half).
  1. Out-of-fold normal scores come from leave-one-run-out training on the training runs.
  2. For q in a grid, T1 = quantile(oof, q); score every candidate on VALIDATION.
  3. Select the q with the best F1 subject to window FPR <= max_fpr (default 5 %).
  4. Report that single choice on TEST, save the bundle (ml/models/<name>.joblib), and write the full sweep.

  python -m ml.operating_point --train datasets/features/train_*.csv --test datasets/features/test_*.csv"""
from __future__ import annotations
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from feature_engine.src.feature_selection import select_features
from feature_engine.src.windowing import feature_columns
from .bundle import Bundle, oof_scores
from .evaluation.detection_eval import evaluate_bundle
from .models import REGISTRY, make
from .train import load_normal

GRID = [0.80, 0.90, 0.95, 0.97, 0.98, 0.99, 0.995]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", nargs="+", required=True)
    ap.add_argument("--test", nargs="+", required=True)
    ap.add_argument("--out", default="results/phase2")
    ap.add_argument("--models-dir", default="ml/models")
    ap.add_argument("--max-fpr", type=float, default=0.05)
    ap.add_argument("--persist", type=int, default=2)
    a = ap.parse_args(argv)
    tr = load_normal(a.train)
    runs = sorted(a.test)
    val = pd.concat([pd.read_csv(p) for p in runs[:len(runs) // 2]], ignore_index=True)
    tst = pd.concat([pd.read_csv(p) for p in runs[len(runs) // 2:]], ignore_index=True)
    cols, _ = select_features(tr, feature_columns(tr))
    sweep, chosen = [], []
    for name in REGISTRY:
        oof = oof_scores(name, tr, cols, {})
        model = make(name).fit(tr, cols)
        for q in GRID:
            t1 = float(np.quantile(oof, q))
            b = Bundle(name, model, cols, t1, max(float(np.quantile(oof, 0.999)), 1.5 * t1), dict(q1=q, n_train=len(tr), threshold_source="leave-one-run-out"))
            for split, df in (("validation", val), ("test", tst)):
                r = evaluate_bundle(b, df, a.persist)["summary"]
                sweep.append(dict(model=name, q=q, split=split, **{k: r[k] for k in (
                    "t1", "roc_auc", "f1", "precision", "recall", "fpr", "event_recall", "median_latency_ms", "persistent_false_alarms", "normal_windows")}))
        sw = pd.DataFrame([s for s in sweep if s["model"] == name and s["split"] == "validation"])
        ok = sw[sw.fpr <= a.max_fpr]
        pick = (ok if len(ok) else sw).sort_values(["f1", "q"], ascending=[False, False]).iloc[0]
        q = float(pick.q)
        t1 = float(np.quantile(oof, q))
        b = Bundle(name, model, cols, t1, max(float(np.quantile(oof, 0.999)), 1.5 * t1),
                   dict(q1=q, n_train=len(tr), threshold_source="leave-one-run-out", selected_on="validation runs", max_fpr=a.max_fpr))
        b.save(Path(a.models_dir) / f"{name}.joblib")
        t = next(s for s in sweep if s["model"] == name and s["split"] == "test" and s["q"] == q)
        chosen.append(dict(model=name, chosen_q=q, **{k: t[k] for k in ("t1", "roc_auc", "f1", "precision", "recall", "fpr", "event_recall",
                           "median_latency_ms", "persistent_false_alarms", "normal_windows")}))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(sweep).to_csv(out / "threshold_sweep.csv", index=False)
    c = pd.DataFrame(chosen)
    c.to_csv(out / "model_comparison_selected.csv", index=False)
    print("Selected on validation runs, reported on held-out TEST runs:")
    print(c.round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
