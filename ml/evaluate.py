#!/usr/bin/env python3
"""Phase-II evaluation: model comparison (E3), feature-group ablation (E4), window-size study (E5).

  python -m ml.evaluate --train datasets/features/train_*.csv --test datasets/features/test_*.csv --out results/phase2"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from feature_engine.src.feature_selection import select_features
from feature_engine.src.windowing import feature_columns
from .bundle import train_bundle
from .evaluation.detection_eval import evaluate_bundle
from .models import REGISTRY
from .train import load_normal

GROUPS = {
    "syscall": lambda c: c.startswith(("sys_", "cat_", "frac_")) and not c.endswith(("_rmean", "_rstd", "_burst", "_delta")),
    "resource": lambda c: c.split("_r")[0] in ("cpu_ns", "cpu_util", "switches", "invol_ratio", "page_faults") and not c.endswith(("_rmean", "_rstd", "_burst", "_delta")),
    "process": lambda c: c in ("n_fork", "n_exec", "n_exit"),
    "temporal": lambda c: c.endswith(("_rmean", "_rstd", "_burst", "_delta")),
}


def split_groups(cols):
    g = {k: [c for c in cols if f(c)] for k, f in GROUPS.items()}
    return g


def run_models(tr, te, cols, persist=2, models=None, q1=0.99):
    out, ev = [], []
    for name in models or REGISTRY:
        b = train_bundle(name, tr, cols, q1=q1)
        r = evaluate_bundle(b, te, persist)
        out.append(r["summary"])
        e = r["events"].assign(model=name)
        ev.append(e)
    return pd.DataFrame(out), pd.concat(ev, ignore_index=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", nargs="+", required=True)
    ap.add_argument("--test", nargs="+", required=True)
    ap.add_argument("--out", default="results/phase2")
    ap.add_argument("--persist", type=int, default=2)
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tr = load_normal(a.train)
    te = pd.concat([pd.read_csv(p) for p in a.test], ignore_index=True)
    cols, _ = select_features(tr, feature_columns(tr))

    summ, ev = run_models(tr, te, cols, a.persist)
    summ.to_csv(out / "model_comparison.csv", index=False)
    ev.to_csv(out / "event_detection.csv", index=False)
    print(summ[["model", "roc_auc", "f1", "precision", "recall", "fpr", "event_recall", "median_latency_ms",
                "persistent_false_alarms", "infer_us_per_window"]].round(3).to_string(index=False))
    per = ev.groupby(["model", "scenario"]).agg(instances=("detected", "size"), detected=("detected", "mean"),
                                                 latency_ms=("latency_ms", "median")).reset_index()
    per.to_csv(out / "per_scenario.csv", index=False)
    print(per.round(2).to_string(index=False))

    # E4 feature-group ablation with the isolation forest, at the operating point chosen on validation runs
    sel = out / "model_comparison_selected.csv"
    q_if = float(pd.read_csv(sel).set_index("model").loc["isolation_forest", "chosen_q"]) if sel.exists() else 0.99
    print("ablation operating point q =", q_if)
    g = split_groups(cols)
    rows = []
    def ab(label, use):
        use = [c for c in cols if c in set(use)]
        if len(use) < 2:
            return
        s, _ = run_models(tr, te, use, a.persist, ["isolation_forest"], q1=q_if)
        r = s.iloc[0]
        rows.append(dict(feature_set=label, n_features=len(use), roc_auc=r.roc_auc, f1=r.f1, recall=r.recall, fpr=r.fpr,
                         event_recall=r.event_recall))
    ab("all", cols)
    for k, v in g.items():
        ab(f"only_{k}", v)
        ab(f"without_{k}", [c for c in cols if c not in set(v)])
    pd.DataFrame(rows).to_csv(out / "feature_ablation.csv", index=False)
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    json.dump({k: len(v) for k, v in g.items()}, open(out / "feature_groups.json", "w"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
