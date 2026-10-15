"""Window-level and event-level detection evaluation (Objective 6, E3-E5).

Window level: every labelled (window, root-pid) row is one sample.
Event level : one anomalous workload instance is DETECTED if >= persist consecutive windows score >= T1;
              detection latency = end of the first flagged window - workload start."""
from __future__ import annotations
import time

import numpy as np
import pandas as pd

from .metrics import detection_metrics


def event_level(te: pd.DataFrame, flagged: np.ndarray, persist: int = 2) -> pd.DataFrame:
    te = te.assign(flag=flagged)
    rows = []
    for (run, pid, sc), g in te[te.label == 1].groupby(["run_id", "pid", "scenario"]):
        g = g.sort_values("widx")
        f, w = g["flag"].to_numpy(), g["widx"].to_numpy()
        det_i = None
        for i in range(len(f) - persist + 1):
            if f[i:i + persist].all() and (w[i + persist - 1] - w[i]) == persist - 1:
                det_i = i
                break
        first = np.argmax(f) if f.any() else None
        rows.append(dict(run_id=run, pid=pid, scenario=sc, windows=len(g), detected=det_i is not None,
                         latency_ms=(g["end_ns"].iloc[det_i + persist - 1] - g["wl_start_ns"].iloc[0]) / 1e6 if det_i is not None else np.nan,
                         first_flag_latency_ms=(g["end_ns"].iloc[first] - g["wl_start_ns"].iloc[0]) / 1e6 if first is not None else np.nan))
    return pd.DataFrame(rows)


def false_alarms(te: pd.DataFrame, flagged: np.ndarray, persist: int = 2) -> dict:
    """Normal-workload windows flagged, and persistent false alarms (>= persist consecutive)."""
    n = te.assign(flag=flagged)
    n = n[n.label == 0]
    runs = 0
    for _, g in n.groupby(["run_id", "pid"]):
        f = g.sort_values("widx")["flag"].to_numpy()
        run = 0
        for x in f:
            run = run + 1 if x else 0
            if run == persist:
                runs += 1
    return dict(normal_windows=len(n), flagged_normal=int(n["flag"].sum()), persistent_false_alarms=runs)


def evaluate_bundle(b, te: pd.DataFrame, persist: int = 2) -> dict:
    te = te[te.label.isin([0, 1])].reset_index(drop=True)
    t = time.perf_counter()
    s = b.score(te)
    infer_us = (time.perf_counter() - t) / max(len(te), 1) * 1e6
    res = detection_metrics(te["label"], s, b.t1)
    res.update(model=b.name, t1=b.t1, t2=b.t2, infer_us_per_window=infer_us, n_test=len(te))
    flag = s >= b.t1
    ev = event_level(te, flag, persist)
    res["event_recall"] = float(ev["detected"].mean()) if len(ev) else float("nan")
    res["median_latency_ms"] = float(ev["latency_ms"].median()) if len(ev) else float("nan")
    res.update(false_alarms(te, flag, persist))
    res["crit_recall"] = float((s[te.label.to_numpy() == 1] >= b.t2).mean())
    return {"summary": res, "events": ev, "scores": s, "te": te}
