# Software Requirements Specification (corrected)

Purpose: requirements of the Linux eBPF runtime anomaly-detection and remediation framework (MCSP34 -> MCSP41).
Users: OS/security researchers, sysadmins, evaluators. Status column: **P1** = implemented in this repo (Phase-I), **P2** = Phase-II.

## 1. Functional requirements
| ID | Requirement | Status | Where |
|----|-------------|--------|-------|
| FR-01 | Load, attach, detach authorised eBPF programs | P1 | `collector/src/loader.c` |
| FR-02 | Monitor process lifecycle (fork/exec/exit) | P1 | `process_monitor.bpf.c` |
| FR-03 | Capture syscall activity of monitored processes | P1 | `syscall_monitor.bpf.c` |
| FR-04 | Collect CPU, context-switch, page-fault indicators (memory/I-O: syscall categories now, block-I/O probe P2) | P1 | `resource_monitor.bpf.c` |
| FR-05 | Transfer events kernel->user efficiently | P1 | ring buffer + drained maps |
| FR-06 | Aggregate by process and time window | P1 | `windowing.py` |
| FR-07 | Compute behavioural features | P1 | `feature_engine/src/*` |
| FR-08 | Anomaly score: >= 1 baseline + >= 1 ML method | P1 baseline / P2 ML | `ml/statistical/baseline.py` |
| FR-09 | Compare detection models | P2 | `ml/evaluation/` |
| FR-10 | Alerts at configurable thresholds | P2 | |
| FR-11 | Configurable response policies | P2 | `remediation/policy_engine` |
| FR-12 | Remediate authorised test processes only | P2 | `remediation/` |
| FR-13 | Audit log of anomalies and actions | P2 | |
| FR-14 | Record CPU, memory, throughput, latency measurements | P1 | `collector_metrics.csv`, `bpf_prog_stats.csv`, `benchmarks/` |
| FR-15 | Visualisation of results. **Optional** (was "shall"); must not be a dependency of the core pipeline | P2 | `dashboard/` |

## 2. Non-functional requirements
| ID | Requirement |
|----|-------------|
| NFR-01 | Low measurable overhead; quantified per BPF program (`run_time_ns / run_cnt`) and end-to-end (E1/E2) |
| NFR-02 | All programs pass the kernel verifier; no unsafe operations; ML inference stays in user space |
| NFR-03 | Collector survives bursts: bounded memory, drops counted not hidden |
| NFR-04 | Supports many concurrent processes (targets map 8192, syscall map 65,536 entries) |
| NFR-05 | Modular kernel/user code |
| NFR-06 | Experiments reproducible by script + config (`scripts/run_experiment.sh`) |
| NFR-07 | Open-source tools only |
| NFR-08 | Remediation restricted to an allow-list of test workloads |
| NFR-09 | Explainability: top contributing features per anomalous window (`RobustZBaseline.explain`) |
| NFR-10 | **Ubuntu 22.04/24.04 on x86-64 or aarch64, kernel >= 5.8 with BTF** (ring buffer, CO-RE); root or CAP_BPF+CAP_PERFMON; tracefs mounted |

## 3. Constraints
Kernel-version dependence of probes; privileged execution; controlled benign workloads only (no malware); remediation never applied to host services.

## 4. Hardware / software
Min: x86-64, 4 cores, 8 GB, 20 GB disk. Recommended 6-8 cores, 16 GB, SSD. No GPU. Packages: `requirements/system-packages.txt`, `requirements/python.txt`.
