"""Real-time detector: tails a running collector's CSV output, builds features per complete window,
scores them with a trained bundle and yields Detection records."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from feature_engine.src.stream import CsvTail, StreamFeatureBuilder
from feature_engine.src.windowing import load_config
from ml.bundle import Bundle


@dataclass
class Detection:
    pid: int
    comm: str
    widx: int
    start_ns: int
    end_ns: int
    score: float
    ratio: float                 # score / T1  (>= 1 suspicious)
    crit_ratio: float            # score / T2  (>= 1 critical)
    level: str                   # normal | suspicious | critical
    top_features: list = field(default_factory=list)
    decided_ns: int = 0          # time.monotonic_ns() when the decision was made


class LiveDetector:
    def __init__(self, run_dir, bundle: Bundle, window_ms: int | None = None, cfg: dict | None = None,
                 wait_meta_s: float = 15.0):
        self.dir, self.bundle = Path(run_dir), bundle
        cfg = dict(cfg or load_config())
        meta_p = self.dir / "meta.json"
        t = time.time()
        while not meta_p.exists() or not meta_p.read_text().strip():
            if time.time() - t > wait_meta_s:
                raise TimeoutError(f"{meta_p} did not appear: is the collector running?")
            time.sleep(0.1)
        self.meta = json.loads(meta_p.read_text())
        cfg["window_ms"] = window_ms or max(int(cfg["window_ms"]), int(self.meta["window_ms"]))
        self.builder = StreamFeatureBuilder(self.meta, cfg, run_id="live")
        self.tails = {k: CsvTail(self.dir / f) for k, f in (
            ("sys", "syscall_windows.csv"), ("res", "resource_windows.csv"),
            ("proc", "process_events.csv"), ("met", "collector_metrics.csv"))}
        self.t0 = self.builder.t0

    def poll(self, only_pids: set[int] | None = None) -> list[Detection]:
        sys_df, res_df = self.tails["sys"].read(), self.tails["res"].read()
        proc_df, met = self.tails["proc"].read(), self.tails["met"].read()
        wm = int(met["ts_ns"].max()) if len(met) else None
        if only_pids is not None:
            # Only registered targets are scored: drop everything else BEFORE feature building. Without this a
            # fork storm (hundreds of short-lived children per second) made the detector fall minutes behind.
            keep = lambda d: d[d["pid"].isin(only_pids)] if len(d) else d
            sys_df, res_df, proc_df = keep(sys_df), keep(res_df), keep(proc_df)
        self.builder.add(sys_df, res_df, proc_df, wm)
        f = self.builder.poll()
        if f.empty:
            return []
        if only_pids is not None:
            f = f[f["pid"].isin(only_pids)]
        if f.empty:
            return []
        for c in self.bundle.cols:
            if c not in f:
                f[c] = 0.0
        s = self.bundle.score(f)
        top = self.bundle.model.explain(f)
        now = time.monotonic_ns()
        out = []
        for (_, r), sc, tp in zip(f.iterrows(), s, top):
            ratio, cr = sc / self.bundle.t1, sc / self.bundle.t2
            out.append(Detection(int(r["pid"]), str(r["comm"]), int(r["widx"]), int(r["start_ns"]), int(r["end_ns"]),
                                 float(sc), float(ratio), float(cr),
                                 "critical" if sc >= self.bundle.t2 else "suspicious" if sc >= self.bundle.t1 else "normal",
                                 tp, now))
        return out
