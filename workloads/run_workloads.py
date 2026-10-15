#!/usr/bin/env python3
"""Run a plan of benign workloads and record ground-truth labels.

  python3 workloads/run_workloads.py --plan workloads/configs/workload_config.yaml \
          --run-id r1 --labels datasets/labels/r1_labels.csv

Writes labels.csv rows: run_id,workload,kind,pid,start_ns,end_ns (CLOCK_MONOTONIC ns,
the same clock as the eBPF timestamps). Only scripts under workloads/{normal,anomalous}
may be executed (allow-list): this tool never launches arbitrary commands."""
import argparse
import csv
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
ALLOWED = {"normal": ROOT / "normal", "anomalous": ROOT / "anomalous"}


def script_for(entry):
    kind, name = entry["kind"], entry["name"]
    if kind not in ALLOWED or "/" in name or name.startswith("."):
        sys.exit(f"refusing entry {entry}: kind must be normal|anomalous, name a bare script name")
    p = ALLOWED[kind] / f"{name}.py"
    if not p.exists():
        sys.exit(f"workload script not found: {p}")
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", default=str(ROOT / "configs" / "workload_config.yaml"))
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--labels", required=True, help="CSV to create/append")
    a = ap.parse_args()

    plan = yaml.safe_load(Path(a.plan).read_text())["schedule"]
    jobs = sorted(plan, key=lambda e: e.get("start_after", 0))
    for e in jobs:
        script_for(e)                                  # validate before starting anything
    t_plan = time.monotonic()
    running, rows = [], []
    for e in jobs:
        wait = e.get("start_after", 0) - (time.monotonic() - t_plan)
        if wait > 0:
            time.sleep(wait)
        cmd = [sys.executable, str(script_for(e)), "--duration", str(e["duration"]),
               "--intensity", e.get("intensity", "medium")]
        start = time.monotonic_ns()
        p = subprocess.Popen(cmd, cwd=ROOT.parent)
        running.append((e, p, start))
    ends = {}
    while len(ends) < len(running):                       # record each job's REAL exit time (not the time we got to wait on it)
        for i, (e, p, start) in enumerate(running):
            if i not in ends and p.poll() is not None:
                ends[i] = time.monotonic_ns()
        time.sleep(0.02)
    for i, (e, p, start) in enumerate(running):
        rows.append([a.run_id, e["name"], e["kind"], p.pid, start, ends[i]])

    new = not os.path.exists(a.labels)
    Path(a.labels).parent.mkdir(parents=True, exist_ok=True)
    with open(a.labels, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["run_id", "workload", "kind", "pid", "start_ns", "end_ns"])
        w.writerows(rows)
    print(f"{len(rows)} workloads finished; labels -> {a.labels}")


if __name__ == "__main__":
    main()
