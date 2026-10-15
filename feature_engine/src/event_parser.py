"""Load a collector run directory into pandas DataFrames (Objective 3, step 1)."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class Run:
    path: Path
    meta: dict
    proc: pd.DataFrame      # ts_ns,event,pid,ppid,uid,gid,value,comm
    sys: pd.DataFrame       # window_start_ns,window_end_ns,pid,comm,nr,count
    res: pd.DataFrame       # window_start_ns,window_end_ns,pid,comm,cpu_ns,switches,invol_switches,page_faults
    metrics: pd.DataFrame
    prog_stats: pd.DataFrame

    @property
    def t0(self) -> int:
        return int(self.meta["start_monotonic_ns"])

    @property
    def t_end(self) -> int:
        return int(self.meta["end_monotonic_ns"])


def _csv(path: Path, **kw) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path, **kw)


def load_run(run_dir: str | Path) -> Run:
    d = Path(run_dir)
    meta_path = d / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"{meta_path} missing: is {d} a collector output directory?")
    meta = json.loads(meta_path.read_text())
    if not meta.get("end_monotonic_ns"):
        raise ValueError(f"{d}: run did not finish cleanly (end_monotonic_ns == 0); re-run the collector")
    return Run(
        path=d,
        meta=meta,
        proc=_csv(d / "process_events.csv"),
        sys=_csv(d / "syscall_windows.csv"),
        res=_csv(d / "resource_windows.csv"),
        metrics=_csv(d / "collector_metrics.csv"),
        prog_stats=_csv(d / "bpf_prog_stats.csv"),
    )
