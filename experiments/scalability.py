#!/usr/bin/env python3
"""E9: can the system monitor many concurrent processes? For N in --counts: run N light workloads for
--seconds with the collector (PID-scoped) and the live detector, record collector CPU/RSS, ring-buffer drops,
map failures and detector processing time per window.

  sudo python -m experiments.scalability --model ml/models/isolation_forest.joblib --counts 1 5 10 25"""
from __future__ import annotations
import argparse
import json
import os
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

from ml.bundle import Bundle
from remediation.safety import Registry
from remediation.supervisor import Supervisor
from runtime.live_detector import LiveDetector
from runtime.pipeline import ROOT


def one(n, a, bundle, out):
    d = out / f"scale_{n}"
    reg, sup = Registry(), None
    sup = Supervisor(reg)
    coll = subprocess.Popen([str(ROOT / "build/ebpf-collector"), "-o", str(d), "-w", "500", "-p", str(os.getpid())],
                            stderr=subprocess.DEVNULL)
    det = LiveDetector(d, bundle, window_ms=1000)
    for i in range(n):
        sup.launch_workload("cpu_workload", "normal", a.seconds + 5, "low")
    t0, proc_t, windows, rows = time.monotonic(), 0.0, 0, 0
    while time.monotonic() - t0 < a.seconds:
        t = time.perf_counter()
        ds = det.poll(set(reg.targets))
        if ds:
            proc_t += time.perf_counter() - t
            windows += len({x.widx for x in ds})
            rows += len(ds)
        time.sleep(0.2)
    sup.cleanup()
    coll.send_signal(signal.SIGINT)
    coll.wait(timeout=10)
    m = pd.read_csv(d / "collector_metrics.csv")
    last = m.iloc[-1]
    prog = pd.read_csv(d / "bpf_prog_stats.csv")
    return dict(processes=n, seconds=a.seconds, scored_rows=rows, windows=windows,
                detector_ms_per_window=1000 * proc_t / max(windows, 1),
                detector_us_per_row=1e6 * proc_t / max(rows, 1),
                collector_cpu_pct=100 * last.collector_cpu_ms / 1000 / a.seconds, collector_rss_mb=last.collector_rss_kb / 1024,
                events_received=int(last.events_received), ringbuf_dropped=int(last.ringbuf_dropped),
                map_failures=int(last.map_failures), bpf_ns_per_run=float(prog.run_time_ns.sum() / max(prog.run_cnt.sum(), 1)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--counts", type=int, nargs="+", default=[1, 5, 10, 25])
    ap.add_argument("--seconds", type=int, default=20)
    ap.add_argument("--out", default="results/phase2/scalability")
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    b = Bundle.load(a.model)
    df = pd.DataFrame([one(n, a, b, out) for n in a.counts])
    df.to_csv(out.parent / "scalability.csv", index=False)
    print(df.round(2).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
