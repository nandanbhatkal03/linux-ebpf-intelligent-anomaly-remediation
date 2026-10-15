"""CPU / scheduling / page-fault features from resource_windows.csv."""
from __future__ import annotations
import pandas as pd


def resource_features(res_long: pd.DataFrame, win_ns: int) -> pd.DataFrame:
    """res_long: columns [widx, pid, cpu_ns, switches, invol_switches, page_faults]."""
    cols = ["widx", "pid", "cpu_ns", "cpu_util", "switches", "invol_ratio", "page_faults"]
    if res_long.empty:
        return pd.DataFrame(columns=cols)
    g = res_long.groupby(["widx", "pid"], as_index=False)[
        ["cpu_ns", "switches", "invol_switches", "page_faults"]].sum()
    g["cpu_util"] = g["cpu_ns"] / win_ns          # fraction of ONE CPU
    g["invol_ratio"] = g["invol_switches"] / g["switches"].clip(lower=1)
    return g[cols]
