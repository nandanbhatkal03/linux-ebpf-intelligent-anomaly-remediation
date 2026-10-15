#!/usr/bin/env python3
"""E7/E8: does controlled remediation reduce the duration/impact of an anomalous workload?

Two arms on identical workloads, same model and policy:
  observe : detection + alerts only (dry_run)  - the control
  active  : policy-controlled remediation
A 'victim' latency probe (not monitored, not remediable) measures application impact.

  sudo python -m experiments.live_remediation --model ml/models/isolation_forest.joblib --scenario cpu_pressure"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from runtime.pipeline import ROOT, main as pipeline_main


def run_arm(arm, a, out):
    log = out / f"{arm}_victim.csv"
    victim = subprocess.Popen([sys.executable, str(ROOT / "workloads/normal/latency_probe.py"), "--duration",
                               str(a.duration + 2), "--log", str(log)])
    args = ["--model", a.model, "--policy", a.policy, "--duration", str(a.duration), "--out", str(out),
            "--run-id", arm, "--workload", f"cpu_workload:normal:{a.duration}:medium",
            "--workload", f"{a.scenario}:anomalous:{a.anomaly_s}:{a.intensity}@{a.anomaly_at}"]
    if arm == "observe":
        args.append("--observe-only")
    pipeline_main(args)
    victim.terminate()
    victim.wait()
    return json.loads((out / arm / "summary.json").read_text())


ONSET = 0.0


def analyse(arm, summary, out):
    ev = summary["events"]
    L = next(w for w in summary["launched"].values() if w["kind"] == "anomalous")
    first = lambda name: next((e for e in ev if e["event"] == name and e.get("pid") == L["pid"]), None)
    alert, exited = first("alert"), first("exited")
    acts = [e for e in ev if e["event"] in ("restrict", "suspend", "terminate") and e.get("pid") == L["pid"]]
    v = pd.read_csv(out / f"{arm}_victim.csv")
    t_launch = L["launch_ns"] + ONSET * 1e9          # anomalous behaviour begins at launch + onset
    pre = v[v.t_mono_ns < t_launch].samples
    t_anom_end = L["exit_ns"] if "exit_ns" in L else t_launch + L["duration"] * 1e9
    during = v[(v.t_mono_ns >= t_launch) & (v.t_mono_ns < t_anom_end)].samples
    after = v[v.t_mono_ns >= t_anom_end].samples
    return dict(arm=arm, scenario=L["name"], detect_s=(alert["t"] - L["start"] - ONSET) if alert else np.nan,
                first_action=acts[0]["event"] if acts else "none",
                first_action_s=(acts[0]["t"] - L["start"] - ONSET) if acts else np.nan,
                action_latency_ms=acts[0]["latency_ms"] if acts else np.nan,
                anomaly_lifetime_s=(exited["t"] - L["start"] - ONSET) if exited else np.nan,
                victim_tput_before=pre.mean(), victim_tput_during=during.mean(), victim_tput_after=after.mean() if len(after) else np.nan,
                victim_tput_during_min=during.min() if len(during) else np.nan,
                false_alert_before_onset=bool(alert and alert["t"] - L["start"] < ONSET))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--policy", default=str(ROOT / "configs/policy.yaml"))
    ap.add_argument("--scenario", default="cpu_pressure")
    ap.add_argument("--intensity", default="high")
    ap.add_argument("--duration", type=float, default=60)
    ap.add_argument("--anomaly-at", type=float, default=15)
    ap.add_argument("--anomaly-s", type=float, default=40)
    ap.add_argument("--out", default="results/phase2/live")
    ap.add_argument("--onset", type=float, default=None, help="seconds after launch at which the process turns anomalous (runaway_cpu: 10)")
    a = ap.parse_args(argv)
    global ONSET
    ONSET = a.onset if a.onset is not None else (10.0 if a.scenario == "runaway_cpu" else 0.0)
    out = Path(a.out) / a.scenario; out.mkdir(parents=True, exist_ok=True)
    rows = [analyse(arm, run_arm(arm, a, out), out) for arm in ("observe", "active")]
    df = pd.DataFrame(rows)
    df.to_csv(out / f"{a.scenario}_comparison.csv", index=False)
    print(df.round(2).T.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
