# Phase-II design: detection -> decision -> remediation

## Real-time path (`runtime/pipeline.py`)
```
build/ebpf-collector -p <pipeline pid>   (PID-scoped: supervised workloads inherit monitoring)
        | CSV appended every window (500 ms)
runtime/live_detector.LiveDetector  -- CsvTail -> StreamFeatureBuilder (same code as batch; tested equal)
        | one Detection per (registered pid, 1 s window): score, ratio=score/T1, level, top features
remediation/policy_engine.PolicyEngine   (pure state machine, unit-tested)
        | Decision: alert | restrict | suspend | terminate | resume | unrestrict
remediation/remediation_engine -> safety.check() -> actions.* -> audit.jsonl + SQLite
```
Only processes launched by the **Supervisor** are registered (allow-list) and scored. Everything else is only observed.

## Policy (`configs/policy.yaml`)
* suspicious = score >= T1 for 2 consecutive windows -> **alert**.
* critical = score >= T2 for 2 windows, or >= T1 for 6 windows -> ladder **restrict (nice 19) -> suspend (SIGSTOP, 3 s hold) -> terminate (SIGTERM, then SIGKILL)**, one rung per 2 windows while the anomaly persists. `max_level` caps the ladder; `dry_run` logs without acting.
* recovery: 5 normal windows lift restrictions / resume.
* warm-up: detections in a target's first 3 s are stored but not acted on (start-up transients dominate false positives of the statistical and isolation-forest models).
* restart: an optional supervised restart of a terminated controlled workload (budget 1).

## Safety (`remediation/safety.py`)
An action is executed only if the pid is (a descendant of) a registered target **with an unchanged start time** (PID-reuse guard), pid > 1, not this process or its parent, not a kernel thread. Alerts never touch processes. Every attempt - including BLOCKED ones - is written to the audit log. Tests cover: unregistered process untouched, dry-run untouched, recycled PID blocked.

## Thresholds
T1/T2 from leave-one-run-out scores of normal windows; the operating quantile q is selected on validation runs and reported on separate test runs (`ml/operating_point.py`).

## CPU accounting fix (affects Phase-I data)
The Phase-I resource monitor credited on-CPU time only at `sched_switch`, so a CPU hog that is never switched out was invisible (found when a lone spinning process produced no feature rows in the live run). The monitor now uses the `sched_stat_runtime` tracepoint (every tick and switch), with the old method as a fallback; `meta.json` records `cpu_accounting`. All Phase-II data was recollected after this fix.
