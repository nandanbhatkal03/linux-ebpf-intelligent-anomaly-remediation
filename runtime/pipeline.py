#!/usr/bin/env python3
"""End-to-end real-time pipeline:  eBPF collector -> streaming features -> model -> policy -> remediation -> audit/DB.

  sudo python -m runtime.pipeline --model ml/models/isolation_forest.joblib --policy configs/policy.yaml \
       --duration 60 --workload cpu_workload:normal:55:medium --workload cpu_pressure:anomalous:40:high@15

Workload spec  NAME:KIND:DURATION:INTENSITY[@START_AFTER][!]   ('!' = restartable). Only these supervised
processes are scored and eligible for remediation; everything else is only observed."""
from __future__ import annotations
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import yaml

from ml.bundle import Bundle
from remediation.audit import AuditLog
from remediation.policy_engine import Policy, PolicyEngine
from remediation.remediation_engine import RemediationEngine
from remediation.safety import Registry
from remediation.supervisor import Supervisor
from runtime.live_detector import LiveDetector
from storage.db import Store

ROOT = Path(__file__).resolve().parents[1]


def parse_spec(s: str):
    restart = s.endswith("!")
    s = s.rstrip("!")
    start = 0.0
    if "@" in s:
        s, a = s.rsplit("@", 1)
        start = float(a)
    n, k, d, i = (s.split(":") + ["medium"])[:4]
    return dict(name=n, kind=k, duration=float(d), intensity=i, start=start, restart=restart)


def run(args) -> dict:
    run_id = args.run_id or f"live-{int(time.time())}"
    outdir = Path(args.out) / run_id
    outdir.mkdir(parents=True, exist_ok=True)
    for stale in ("results.db", "audit.jsonl", "summary.json"):
        (outdir / stale).unlink(missing_ok=True)
    import shutil
    shutil.rmtree(outdir / "collector", ignore_errors=True)
    bundle = Bundle.load(args.model)
    pol = yaml.safe_load(Path(args.policy).read_text()) if args.policy else {}
    pol = Policy.from_dict(pol.get("policy", pol))
    if args.observe_only:
        pol.dry_run = True
    reg = Registry()
    sup = Supervisor(reg)
    audit = AuditLog(outdir / "audit.jsonl", run_id)
    store = Store(outdir / "results.db")
    store.start_run(run_id, bundle.name, json.dumps(pol.__dict__), "observe-only" if args.observe_only else "active")
    engine = PolicyEngine(pol)
    rem = RemediationEngine(reg, audit, pol.dry_run, store, run_id, sup, pol.restart_on_terminate)

    # collector: scoped to this process tree (children inherit monitoring) -> low overhead, many-process scalable
    coll_dir = outdir / "collector"
    coll = subprocess.Popen([str(ROOT / "build" / "ebpf-collector"), "-o", str(coll_dir), "-w", str(args.window_ms),
                             "-p", str(os.getpid())], stderr=open(outdir / "collector.log", "w"))
    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.update(flag=True))
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    events, all_dets = [], []
    try:
        det = LiveDetector(coll_dir, bundle, window_ms=args.feature_ms)
        t_begin = time.monotonic()
        pending = sorted((parse_spec(s) for s in args.workload), key=lambda w: w["start"])
        launched: dict[int, dict] = {}
        while not stop["flag"] and time.monotonic() - t_begin < args.duration:
            now = time.monotonic() - t_begin
            while pending and pending[0]["start"] <= now:
                w = pending.pop(0)
                pid = sup.launch_workload(w["name"], w["kind"], w["duration"], w["intensity"], w["restart"])
                w["pid"], w["launch_ns"] = pid, time.monotonic_ns()
                launched[pid] = w
                audit.write(pid=pid, comm=w["name"], action="launch", ok=True, detail=json.dumps(w), kind=w["kind"])
                events.append(dict(t=now, event="launch", **w))
            for pid, w in launched.items():
                if "exit_ns" not in w and sup.procs[pid].poll() is not None:
                    w["exit_ns"] = time.monotonic_ns()
                    events.append(dict(t=now, event="exited", pid=pid, name=w["name"], code=sup.procs[pid].returncode))
            if coll.poll() is not None:
                raise RuntimeError("collector exited: " + (outdir / "collector.log").read_text()[-300:])
            ds = det.poll(set(reg.targets))
            store.detections(run_id, ds)
            all_dets.extend(ds)
            for d in ds:
                w = launched.get(d.pid)
                if w is not None and d.start_ns < w["launch_ns"] + pol.warmup_s * 1e9:
                    continue                      # warm-up: stored in the DB, not fed to the policy
                for dec in engine.on_detection(d, d.decided_ns):
                    rec = rem.execute(dec, d.comm, d.decided_ns)
                    events.append(dict(t=time.monotonic() - t_begin, event=dec.action, pid=d.pid, ok=rec["ok"], ratio=d.ratio,
                                       latency_ms=rec["latency_ms"], detail=rec["detail"]))
            for dec in engine.on_tick(time.monotonic_ns()):
                t = reg.targets.get(dec.pid)
                rec = rem.execute(dec, t.name if t else "?")
                events.append(dict(t=time.monotonic() - t_begin, event=dec.action, pid=dec.pid, ok=rec["ok"], detail=rec["detail"]))
            time.sleep(args.poll_s)
    finally:
        sup.cleanup()
        coll.send_signal(signal.SIGINT)
        try:
            coll.wait(timeout=10)
        except subprocess.TimeoutExpired:
            coll.kill()
        audit.close()
        store.close()
    summary = dict(run_id=run_id, model=bundle.name, t1=bundle.t1, t2=bundle.t2, policy=pol.__dict__, events=events,
                   detections=len(all_dets), launched={str(k): v for k, v in launched.items()})
    (outdir / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--policy", default=str(ROOT / "configs" / "policy.yaml"))
    ap.add_argument("--workload", action="append", default=[])
    ap.add_argument("--duration", type=float, default=60)
    ap.add_argument("--window-ms", type=int, default=500, help="collector window")
    ap.add_argument("--feature-ms", type=int, default=1000, help="feature window (multiple of the collector window)")
    ap.add_argument("--poll-s", type=float, default=0.2)
    ap.add_argument("--out", default="results/live")
    ap.add_argument("--run-id")
    ap.add_argument("--observe-only", action="store_true", help="detect + alert but never act (control arm)")
    a = ap.parse_args(argv)
    if os.geteuid() != 0:
        print("warning: not root; loading BPF programs needs sudo", file=sys.stderr)
    s = run(a)
    n = {}
    for e in s["events"]:
        n[e["event"]] = n.get(e["event"], 0) + 1
    print(json.dumps(dict(run_id=s["run_id"], detections=s["detections"], event_counts=n), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
