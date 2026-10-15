"""Assemble per-(window, PID) behavioural feature vectors (Objective 3).

Pipeline:  Run -> assign window index -> syscall/process/resource features
           -> outer-merge -> drop incomplete tail window -> temporal features.
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .event_parser import Run
from .process_features import process_features
from .resource_features import resource_features
from .syscall_features import CATEGORIES, build_category_map, syscall_features, syscall_names
from .temporal_features import add_temporal

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "feature_config.yaml"
ID_COLS = ["run_id", "widx", "start_ns", "end_ns", "pid", "comm"]


def load_config(path: str | Path | None = None) -> dict:
    return yaml.safe_load(Path(path or DEFAULT_CONFIG).read_text())


def _assign_window(df: pd.DataFrame, t0: int, win_ns: int) -> pd.DataFrame:
    """Window index from the MIDPOINT of each collector window (robust to jitter)."""
    out = df.copy()
    out["widx"] = (((out["window_start_ns"] + out["window_end_ns"]) // 2 - t0) // win_ns).astype(int)
    return out[out["widx"] >= 0]


def _modal_comm(frames: list[pd.DataFrame]) -> pd.Series:
    rows = [f[["pid", "comm"]] for f in frames if f is not None and not f.empty and "comm" in f]
    if not rows:
        return pd.Series(dtype=object)
    allc = pd.concat(rows)
    return allc.groupby("pid")["comm"].agg(lambda s: s.mode().iloc[0] if not s.mode().empty else "?")


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Numeric model inputs (everything except identifiers/labels)."""
    skip = set(ID_COLS) | {"label", "scenario"}
    return [c for c in df.columns if c not in skip and pd.api.types.is_numeric_dtype(df[c])]


def build_features(run: Run, cfg: dict | None = None, run_id: str | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    win_ms = int(cfg["window_ms"])
    coll_ms = int(run.meta["window_ms"])
    if win_ms % coll_ms:
        raise ValueError(f"feature window {win_ms} ms must be a multiple of the collector window {coll_ms} ms "
                         f"(re-collect with -w {win_ms} or smaller)")
    win_ns, t0 = win_ms * 1_000_000, run.t0
    n_complete = (run.t_end - t0) // win_ns            # last partial window is discarded

    names = syscall_names(run.meta.get("arch"))
    cat_map = build_category_map(cfg["syscall_categories"], cfg.get("default_category", "other"), names)

    sys_l = _assign_window(run.sys, t0, win_ns) if not run.sys.empty else pd.DataFrame(
        columns=["widx", "pid", "nr", "count"])
    res_l = _assign_window(run.res, t0, win_ns) if not run.res.empty else pd.DataFrame(
        columns=["widx", "pid", "cpu_ns", "switches", "invol_switches", "page_faults"])

    sysf = syscall_features(sys_l[["widx", "pid", "nr", "count"]], win_ms / 1000.0, cat_map)
    resf = resource_features(res_l, win_ns)
    procf = process_features(run.proc, t0, win_ns)

    df = sysf.merge(resf, on=["widx", "pid"], how="outer").merge(procf, on=["widx", "pid"], how="outer")
    df = df[(df["widx"] >= 0) & (df["widx"] < n_complete)].copy()
    num = [c for c in df.columns if c not in ("widx", "pid")]
    df[num] = df[num].fillna(0.0)
    keep = (df["sys_total"] >= cfg.get("min_activity", 1)) | (df["cpu_ns"] > 0)
    df = df[keep].reset_index(drop=True)
    if df.empty:
        return df

    comm = _modal_comm([sys_l, res_l, run.proc])
    df["comm"] = df["pid"].map(comm).fillna("?")
    df["run_id"] = run_id or run.meta.get("run_id", run.path.name)
    df["start_ns"] = t0 + df["widx"].astype("int64") * win_ns
    df["end_ns"] = df["start_ns"] + win_ns

    t = cfg.get("temporal", {})
    base = [b for b in t.get("base_features", []) if b in df.columns]
    if base:
        df = add_temporal(df, base, int(t.get("history", 5)))
    front = ID_COLS
    return df[front + [c for c in df.columns if c not in front]]
