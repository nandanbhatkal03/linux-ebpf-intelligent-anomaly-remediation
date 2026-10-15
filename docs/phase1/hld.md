# High-Level Design

```
workloads (normal / controlled anomalous)
        |
 Linux kernel --tracepoints--> eBPF programs (3) --> maps / ring buffer
                                                         |
                       collector (C, libbpf, CO-RE) <----+   drains every window
                                |  raw CSV: process_events, syscall_windows, resource_windows,
                                |           collector_metrics, bpf_prog_stats, meta.json
                      feature_engine (Python) -> features.csv (+ labels from workload runner)
                                |
                         ml/ (P1: robust-z baseline; P2: Isolation Forest, autoencoder)
                                |
                  policy engine -> remediation engine (P2)  ->  results / dashboard (P2)
```

| Component | Responsibility | Key decision |
|-----------|----------------|--------------|
| eBPF layer | observe fork/exec/exit, syscalls, sched_switch, page faults | `tp_btf` for hot paths (lower overhead, typed args); aggregate **in kernel** to avoid event loss |
| Collector | load/attach, drain once per window, self-metrics | one shared `targets` map (PID filter + inheritance across skeletons); read-and-delete per window |
| Feature engine | window x tgid vectors, temporal stats, labels | history excludes the current window; incomplete tail window dropped |
| Detection (P1 baseline) | robust z-score over normal training windows | explainable, cheap reference for Phase-II models |
| Policy / remediation (P2) | severity -> action, allow-list only | non-destructive first |
| Dashboard (P2) | optional | never a dependency |

Clock: all timestamps are `CLOCK_MONOTONIC` ns (identical in kernel `bpf_ktime_get_ns` and user space), so workload labels and events align exactly.
