#!/usr/bin/env python3
"""Train the three models on NORMAL windows (label == 0) and save bundles to ml/models/.

  python -m ml.train datasets/features/train_*.csv --out ml/models [--models isolation_forest autoencoder]"""
from __future__ import annotations
import argparse
import time
from pathlib import Path

import pandas as pd

from feature_engine.src.feature_selection import select_features
from feature_engine.src.windowing import feature_columns
from .bundle import train_bundle
from .models import REGISTRY


def load_normal(paths) -> pd.DataFrame:
    df = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    return df[df["label"] == 0].reset_index(drop=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("features", nargs="+")
    ap.add_argument("--out", default="ml/models")
    ap.add_argument("--models", nargs="+", default=list(REGISTRY))
    ap.add_argument("--q1", type=float, default=0.99)
    ap.add_argument("--q2", type=float, default=0.999)
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    df = load_normal(a.features)
    cols, dropped = select_features(df, feature_columns(df))
    print(f"train rows={len(df)} runs={df.run_id.nunique()} features={len(cols)} (dropped {len(dropped)})")
    for name in a.models:
        t = time.time()
        b = train_bundle(name, df, cols, q1=a.q1, q2=a.q2)
        b.meta["train_seconds"] = round(time.time() - t, 2)
        path = Path(a.out) / f"{name}{a.tag}.joblib"
        b.save(path)
        print(f"{name:17s} T1={b.t1:.4g} T2={b.t2:.4g} ({b.meta['threshold_source']}, {b.meta['train_seconds']}s) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
