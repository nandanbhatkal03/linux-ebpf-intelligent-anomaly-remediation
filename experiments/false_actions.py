#!/usr/bin/env python3
"""Safety experiment: with ONLY normal workloads, how many alerts / remediation actions does the live system take?
  sudo python -m experiments.false_actions --model ml/models/autoencoder.joblib --duration 90"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from runtime.pipeline import ROOT, main as pipeline_main


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--duration", type=float, default=90)
    ap.add_argument("--out", default="results/phase2/live")
    a = ap.parse_args(argv)
    pipeline_main(["--model", a.model, "--duration", str(a.duration), "--out", a.out, "--run-id", "normal_only",
                   "--workload", f"cpu_workload:normal:{a.duration}:medium", "--workload", f"mixed_workload:normal:{a.duration}:medium",
                   "--workload", f"io_workload:normal:{a.duration}:low"])
    s = json.loads((Path(a.out) / "normal_only" / "summary.json").read_text())
    n = {}
    for e in s["events"]:
        n[e["event"]] = n.get(e["event"], 0) + 1
    res = dict(duration_s=a.duration, targets=3, windows_scored=s["detections"], alerts=n.get("alert", 0),
               restrict=n.get("restrict", 0), suspend=n.get("suspend", 0), terminate=n.get("terminate", 0))
    res["destructive_false_actions"] = res["suspend"] + res["terminate"]
    Path(a.out, "false_actions.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
