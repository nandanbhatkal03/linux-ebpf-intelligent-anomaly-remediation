#!/usr/bin/env python3
"""E5: effect of the temporal window size on detection quality and latency.
Re-windows the SAME raw collector runs at several window sizes (collected at the smallest), retrains and re-evaluates.

  python -m experiments.window_study --train-runs datasets/raw/local/train_* --test-runs datasets/raw/local/test_* \
       --sizes 500 1000 2000 5000 --model isolation_forest"""
from __future__ import annotations
import argparse
from pathlib import Path

import pandas as pd

from feature_engine.src.event_parser import load_run
from feature_engine.src.labeling import apply_labels
from feature_engine.src.windowing import build_features, feature_columns, load_config
from feature_engine.src.feature_selection import select_features
from ml.bundle import train_bundle
from ml.evaluation.detection_eval import evaluate_bundle


def featurize(runs, labels_dir, win_ms):
    cfg = load_config(); cfg["window_ms"] = win_ms
    out = []
    for r in runs:
        run = load_run(r)
        f = build_features(run, cfg)
        lab = pd.read_csv(Path(labels_dir) / f"{Path(r).name}_labels.csv")
        out.append(apply_labels(f, run.proc, lab))
    return pd.concat(out, ignore_index=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train-runs", nargs="+", required=True)
    ap.add_argument("--test-runs", nargs="+", required=True)
    ap.add_argument("--labels", default="datasets/labels")
    ap.add_argument("--sizes", type=int, nargs="+", default=[500, 1000, 2000, 5000])
    ap.add_argument("--model", default="isolation_forest")
    ap.add_argument("--out", default="results/phase2/window_size.csv")
    a = ap.parse_args(argv)
    rows = []
    for w in a.sizes:
        tr = featurize(a.train_runs, a.labels, w); tr = tr[tr.label == 0]
        te = featurize(a.test_runs, a.labels, w)
        cols, _ = select_features(tr, feature_columns(tr))
        # persistence is expressed in TIME (2 s) so that windows of different sizes are comparable
        persist = max(1, round(2000 / w))
        r = evaluate_bundle(train_bundle(a.model, tr, cols), te, persist)["summary"]
        rows.append(dict(window_ms=w, train_rows=len(tr), roc_auc=r["roc_auc"], f1=r["f1"], recall=r["recall"], fpr=r["fpr"],
                         event_recall=r["event_recall"], median_latency_ms=r["median_latency_ms"],
                         persistent_false_alarms=r["persistent_false_alarms"], persist_windows=persist))
        print(rows[-1])
    pd.DataFrame(rows).to_csv(a.out, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
