#!/usr/bin/env python3
"""CLI: collector run directories -> features.csv (+ optional ground-truth labels).

  python -m feature_engine.src.build_features datasets/raw/local/run1 -o datasets/features/run1.csv \
         --window-ms 1000 --labels datasets/labels/run1_labels.csv
"""
from __future__ import annotations
import argparse
from pathlib import Path

import pandas as pd

from .event_parser import load_run
from .labeling import apply_labels
from .windowing import build_features, load_config


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", help="collector output directories")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--window-ms", type=int)
    ap.add_argument("--config")
    ap.add_argument("--labels", help="labels.csv written by workloads/run_workloads.py (applies to every run)")
    ap.add_argument("--label-scope", choices=["root", "tree"], default="root",
                    help="root: label only the workload process; tree: descendants inherit (default root)")
    a = ap.parse_args(argv)

    cfg = load_config(a.config)
    if a.window_ms:
        cfg["window_ms"] = a.window_ms
    labels = pd.read_csv(a.labels) if a.labels else None
    frames = []
    for r in a.runs:
        run = load_run(r)
        f = build_features(run, cfg)
        if labels is not None:
            lab = labels[labels["run_id"] == f["run_id"].iloc[0]] if len(f) else labels
            f = apply_labels(f, run.proc, lab, a.label_scope)
        frames.append(f)
        print(f"{r}: {len(f)} (window,pid) rows")
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    print(f"wrote {a.out}: {out.shape[0]} rows x {out.shape[1]} cols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
