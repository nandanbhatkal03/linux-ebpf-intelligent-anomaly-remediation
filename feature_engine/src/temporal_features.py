"""Temporal features: rolling mean/std, burstiness, change score per PID."""
from __future__ import annotations
import numpy as np
import pandas as pd


def add_temporal(df: pd.DataFrame, base: list[str], history: int) -> pd.DataFrame:
    """Adds, for each base feature f: f_rmean, f_rstd, f_burst, f_delta.
    A PID that is silent inside its lifetime counts as zero activity, so each
    PID's series is reindexed over [first_window, last_window]."""
    parts = []
    for pid, g in df.groupby("pid", sort=False):
        g = g.set_index("widx").sort_index()
        full = g.reindex(range(int(g.index.min()), int(g.index.max()) + 1))
        for f in base:
            s = full[f].fillna(0.0)
            prior = s.shift(1)                       # history EXCLUDES the current window
            rm = prior.rolling(history, min_periods=1).mean()
            rs = prior.rolling(history, min_periods=2).std().fillna(0.0)
            full[f"{f}_rmean"] = rm.fillna(0.0)
            full[f"{f}_rstd"] = rs
            denom = (rs + rm).replace(0, np.nan)
            full[f"{f}_burst"] = ((rs - rm) / denom).fillna(0.0)      # Goh-Barabasi B in [-1,1]
            full[f"{f}_delta"] = (s - rm.fillna(s)).abs()
        full["pid"] = pid
        parts.append(full.loc[g.index].reset_index())
    return pd.concat(parts, ignore_index=True) if parts else df
