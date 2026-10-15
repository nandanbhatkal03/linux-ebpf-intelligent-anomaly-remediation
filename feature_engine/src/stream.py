"""Streaming (near-real-time) feature construction.

A StreamFeatureBuilder is fed the same rows the collector appends to its CSVs and emits one feature
DataFrame per COMPLETE window, by running the batch pipeline (`build_features`) over a short sliding
buffer. Re-using the batch code guarantees train/serve consistency (no feature skew). The buffer holds
`history + 1` windows, so temporal features match batch output for processes that stay active
(tests/test_stream.py checks equivalence)."""
from __future__ import annotations
from pathlib import Path

import pandas as pd

from .event_parser import Run
from .windowing import build_features, load_config

EMPTY_SYS = ["window_start_ns", "window_end_ns", "pid", "comm", "nr", "count"]
EMPTY_RES = ["window_start_ns", "window_end_ns", "pid", "comm", "cpu_ns", "switches", "invol_switches", "page_faults"]
EMPTY_PROC = ["ts_ns", "event", "pid", "ppid", "uid", "gid", "value", "comm"]


class CsvTail:
    """Incrementally reads appended CSV lines; keeps a partial trailing line for the next poll."""

    def __init__(self, path: Path):
        self.path, self.off, self.rest, self.header = Path(path), 0, "", None

    def read(self) -> pd.DataFrame:
        if not self.path.exists():
            return pd.DataFrame()
        with open(self.path, "r") as f:
            f.seek(self.off)
            chunk = f.read()
            self.off = f.tell()
        data = self.rest + chunk
        lines = data.split("\n")
        self.rest = lines.pop()                       # "" if the chunk ended on a newline
        if self.header is None and lines:
            self.header = lines.pop(0).split(",")
        if not lines or self.header is None:
            return pd.DataFrame(columns=self.header or [])
        rows = [ln.split(",") for ln in lines if ln]
        rows = [r for r in rows if len(r) == len(self.header)]
        df = pd.DataFrame(rows, columns=self.header)
        for c in df.columns:
            if c not in ("comm", "event"):
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.dropna()


class StreamFeatureBuilder:
    def __init__(self, meta: dict, cfg: dict | None = None, run_id: str = "live"):
        self.cfg = cfg or load_config()
        self.meta, self.run_id = dict(meta), run_id
        self.coll_ms = int(meta["window_ms"])
        self.win_ns = int(self.cfg["window_ms"]) * 1_000_000
        self.coll_ns = self.coll_ms * 1_000_000
        if self.win_ns % self.coll_ns:
            raise ValueError("feature window must be a multiple of the collector window")
        self.t0 = int(meta["start_monotonic_ns"])
        self.hist = int(self.cfg.get("temporal", {}).get("history", 5))
        self.sys = pd.DataFrame(columns=EMPTY_SYS)
        self.res = pd.DataFrame(columns=EMPTY_RES)
        self.proc = pd.DataFrame(columns=EMPTY_PROC)
        self.next_widx = 0
        self.watermark = self.t0

    def add(self, sys_df=None, res_df=None, proc_df=None, watermark_ns: int | None = None):
        for attr, df in (("sys", sys_df), ("res", res_df), ("proc", proc_df)):
            if df is not None and len(df):
                cur = getattr(self, attr)
                new = df if cur.empty else pd.concat([cur, df], ignore_index=True)
                for c in new.columns:                     # keep numeric dtypes (empty seed frames are object)
                    if c not in ("comm", "event"):
                        new[c] = pd.to_numeric(new[c])
                setattr(self, attr, new.reset_index(drop=True))
        if watermark_ns:
            self.watermark = max(self.watermark, int(watermark_ns))

    def _complete_until(self) -> int:
        return max(0, (self.watermark - self.t0 - self.coll_ns) // self.win_ns)

    def poll(self) -> pd.DataFrame:
        out, last = [], self._complete_until()
        while self.next_widx < last:
            k = self.next_widx
            f = self._window(k)
            if len(f):
                out.append(f)
            self.next_widx += 1
        self._trim()
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

    def _window(self, k: int) -> pd.DataFrame:
        kmin = max(0, k - self.hist)
        t0p = self.t0 + kmin * self.win_ns
        mid = lambda d: (d["window_start_ns"] + d["window_end_ns"]) // 2
        s = self.sys[mid(self.sys) >= t0p] if len(self.sys) else self.sys
        r = self.res[mid(self.res) >= t0p] if len(self.res) else self.res
        p = self.proc[self.proc["ts_ns"] >= t0p] if len(self.proc) else self.proc
        meta = dict(self.meta, start_monotonic_ns=t0p, end_monotonic_ns=t0p + (k - kmin + 1) * self.win_ns)
        run = Run(Path("."), meta, p, s, r, pd.DataFrame(), pd.DataFrame())
        f = build_features(run, self.cfg, run_id=self.run_id)
        if f.empty:
            return f
        f = f[f["widx"] == (k - kmin)].copy()
        f["widx"] = k
        f["start_ns"] = self.t0 + k * self.win_ns
        f["end_ns"] = f["start_ns"] + self.win_ns
        return f

    def _trim(self):
        keep_from = self.t0 + max(0, self.next_widx - self.hist - 1) * self.win_ns
        for attr, col in (("sys", "window_end_ns"), ("res", "window_end_ns"), ("proc", "ts_ns")):
            d = getattr(self, attr)
            if len(d):
                setattr(self, attr, d[d[col] >= keep_from].reset_index(drop=True))
