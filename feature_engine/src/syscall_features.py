"""Syscall-derived features: volume, diversity, entropy, category mix."""
from __future__ import annotations
import fnmatch
import json
import platform
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
CATEGORIES = ["process", "memory", "network", "ipc", "file", "other"]


@lru_cache(maxsize=4)
def syscall_names(arch: str | None = None) -> dict[int, str]:
    arch = arch or platform.machine()
    p = CONFIG_DIR / f"syscalls_{arch}.json"
    if not p.exists():
        return {}
    return {int(k): v for k, v in json.loads(p.read_text()).items()}


def build_category_map(rules: dict, default: str, names: dict[int, str], max_nr: int = 512) -> dict[int, str]:
    out = {}
    for nr in range(max_nr):
        name = names.get(nr)
        cat = default
        if name:
            for c, patterns in rules.items():
                if any(fnmatch.fnmatchcase(name, p) for p in patterns):
                    cat = c
                    break
        out[nr] = cat
    return out


def shannon_entropy(counts: np.ndarray) -> float:
    counts = counts[counts > 0].astype(float)
    if counts.size == 0:
        return 0.0
    p = counts / counts.sum()
    return float(-(p * np.log2(p)).sum())


def syscall_features(sys_long: pd.DataFrame, win_s: float, cat_map: dict[int, str]) -> pd.DataFrame:
    """sys_long: columns [widx, pid, nr, count] -> one row per (widx, pid)."""
    if sys_long.empty:
        return pd.DataFrame(columns=["widx", "pid", "sys_total", "sys_unique", "sys_entropy", "sys_rate"])
    df = sys_long.groupby(["widx", "pid", "nr"], as_index=False)["count"].sum()
    g = df.groupby(["widx", "pid"])["count"]
    feat = pd.DataFrame({
        "sys_total": g.sum(),
        "sys_unique": g.size(),
        "sys_entropy": g.apply(lambda s: shannon_entropy(s.to_numpy())),
    }).reset_index()
    feat["sys_rate"] = feat["sys_total"] / win_s
    df["cat"] = df["nr"].map(cat_map).fillna("other")
    cat = df.pivot_table(index=["widx", "pid"], columns="cat", values="count", aggfunc="sum", fill_value=0)
    for c in CATEGORIES:
        if c not in cat.columns:
            cat[c] = 0
    cat = cat[CATEGORIES].add_prefix("cat_").reset_index()
    out = feat.merge(cat, on=["widx", "pid"], how="left")
    for c in CATEGORIES:
        out[f"frac_{c}"] = out[f"cat_{c}"] / out["sys_total"].clip(lower=1)
    return out
