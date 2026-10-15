"""Ground-truth labelling from the workload orchestrator's labels.csv.

labels.csv columns: run_id,workload,kind,pid,start_ns,end_ns
  kind: 'normal' | 'anomalous'; times are CLOCK_MONOTONIC ns (same clock as eBPF).
A (window, PID) row is labelled from the workload whose ROOT pid is the row's pid
or an ancestor (via fork events). label: 1 = anomalous, 0 = normal workload,
-1 = unlabelled background (kernel threads, daemons). Windows must overlap the
workload's [start, end] interval."""
from __future__ import annotations
import pandas as pd

from .process_features import lineage


def _root_of(pid: int, parent: dict[int, int], roots: set[int]) -> int | None:
    seen = 0
    while pid and seen < 64:
        if pid in roots:
            return pid
        pid = parent.get(pid, 0)
        seen += 1
    return None


def apply_labels(features: pd.DataFrame, proc: pd.DataFrame, labels: pd.DataFrame,
                 scope: str = "root") -> pd.DataFrame:
    """scope='root': only the workload's own process is labelled; its descendants stay -1
    (excluded). Needed because a fork storm is anomalous at the PARENT (high n_fork) while each
    short-lived child, viewed alone, is unremarkable. scope='tree': descendants inherit the label."""
    df = features.copy()
    df["label"] = -1
    df["scenario"] = ""
    if labels is None or labels.empty or df.empty:
        return df
    parent = lineage(proc)
    by_root = {int(r.pid): r for r in labels.itertuples()}
    roots = set(by_root)
    cache: dict[int, int | None] = {}
    for i, (pid, s, e) in enumerate(zip(df["pid"], df["start_ns"], df["end_ns"])):
        pid = int(pid)
        if pid not in cache:
            cache[pid] = _root_of(pid, parent, roots)
        root = cache[pid]
        if root is None:
            continue
        if scope == "root" and root != pid:
            continue
        w = by_root[root]
        if s < w.end_ns and e > w.start_ns:       # window overlaps the workload interval
            df.iat[i, df.columns.get_loc("label")] = 1 if w.kind == "anomalous" else 0
            df.iat[i, df.columns.get_loc("scenario")] = w.workload
    return df
