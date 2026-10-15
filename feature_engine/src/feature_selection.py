"""Simple, explainable feature selection: variance + correlation filters."""
from __future__ import annotations
import numpy as np
import pandas as pd


def select_features(df: pd.DataFrame, cols: list[str], var_eps: float = 1e-12,
                    corr_max: float = 0.98) -> tuple[list[str], dict[str, str]]:
    dropped: dict[str, str] = {}
    keep = []
    for c in cols:
        if df[c].var() <= var_eps:
            dropped[c] = "constant"
        else:
            keep.append(c)
    if len(keep) > 1:
        corr = df[keep].corr().abs().fillna(0.0)
        upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
        for c in upper.columns:
            partner = upper.index[upper[c] > corr_max]
            if len(partner) and c not in dropped:
                dropped[c] = f"corr>{corr_max} with {partner[0]}"
        keep = [c for c in keep if c not in dropped]
    return keep, dropped
