"""Process-lifecycle features from fork/exec/exit events."""
from __future__ import annotations
import pandas as pd


def process_features(proc: pd.DataFrame, t0: int, win_ns: int) -> pd.DataFrame:
    cols = ["widx", "pid", "n_fork", "n_exec", "n_exit"]
    if proc is None or proc.empty:
        return pd.DataFrame(columns=cols)
    p = proc.copy()
    p["widx"] = ((p["ts_ns"] - t0) // win_ns).astype(int)
    p = p[p["widx"] >= 0]
    cnt = p.pivot_table(index=["widx", "pid"], columns="event", values="ts_ns", aggfunc="count", fill_value=0)
    for e in ("fork", "exec", "exit"):
        if e not in cnt.columns:
            cnt[e] = 0
    cnt = cnt.rename(columns={"fork": "n_fork", "exec": "n_exec", "exit": "n_exit"})[["n_fork", "n_exec", "n_exit"]]
    return cnt.reset_index()


def lineage(proc: pd.DataFrame) -> dict[int, int]:
    """child tgid -> parent tgid, from fork events (value = child)."""
    if proc is None or proc.empty:
        return {}
    f = proc[proc["event"] == "fork"]
    return {int(c): int(p) for p, c in zip(f["pid"], f["value"])}
