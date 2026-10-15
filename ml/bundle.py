"""A trained model + the thresholds the policy engine needs, persisted with joblib.

T1 (suspicious) and T2 (critical) come from OUT-OF-FOLD scores of normal windows (leave-one-run-out),
so thresholds are not optimistic about unseen normal behaviour."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .models import make


@dataclass
class Bundle:
    name: str
    model: object
    cols: list
    t1: float
    t2: float
    meta: dict = field(default_factory=dict)

    def score(self, df: pd.DataFrame) -> np.ndarray:
        return self.model.score(df)

    def save(self, path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @staticmethod
    def load(path) -> "Bundle":
        return joblib.load(path)


def oof_scores(name: str, df: pd.DataFrame, cols: list, params: dict, group="run_id") -> np.ndarray:
    runs = df[group].unique()
    out = np.zeros(len(df))
    if len(runs) < 2:                        # not enough runs: fall back to in-sample (flagged in meta)
        return make(name, **params).fit(df, cols).score(df)
    for r in runs:
        m = df[group] == r
        out[m.to_numpy()] = make(name, **params).fit(df[~m], cols).score(df[m])
    return out


def train_bundle(name: str, df: pd.DataFrame, cols: list, params: dict | None = None,
                 q1: float = 0.99, q2: float = 0.999, min_ratio: float = 1.5) -> Bundle:
    params = params or {}
    oof = oof_scores(name, df, cols, params)
    t1 = float(np.quantile(oof, q1))
    t2 = float(max(np.quantile(oof, q2), min_ratio * t1))
    model = make(name, **params).fit(df, cols)
    meta = dict(n_train=len(df), n_runs=int(df["run_id"].nunique()), q1=q1, q2=q2, params=params,
                oof_median=float(np.median(oof)), threshold_source="leave-one-run-out" if df["run_id"].nunique() > 1 else "in-sample")
    return Bundle(name, model, list(cols), t1, t2, meta)
