# Project proposal
**Title:** An eBPF-Based Intelligent Framework for Real-Time Linux System Anomaly Detection and Automated Process Remediation (MCSP34 -> MCSP41)

**Problem:** deliver low-overhead kernel telemetry, behavioural anomaly detection and policy-controlled process remediation in one measurable pipeline.

## Objectives and where they live
| # | Objective | Phase | Deliverable in this repo |
|---|-----------|-------|--------------------------|
| 1 | Study Linux monitoring mechanisms | P1 | `literature_review.md`, `/proc` polling baseline in `benchmarks/overhead` (add `strace`) |
| 2 | eBPF telemetry layer | P1 | `ebpf/`, `collector/` |
| 3 | Behavioural features | P1 | `feature_engine/` |
| 4 | Anomaly detection (statistical, IF, AE) | P1 baseline / P2 | `ml/statistical/baseline.py`; IF + AE next |
| 5 | Policy-controlled remediation | P2 | `remediation/` (not yet built) |
| 6 | Detection + system evaluation | P1 partial | `ml/evaluation/metrics.py`, `benchmarks/`, collector self-metrics |

Research questions, hypotheses H1-H4 and experiments E1-E10: unchanged from the package (sections 6, 31, 32).
