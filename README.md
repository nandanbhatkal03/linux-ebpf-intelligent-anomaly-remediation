# Intelligent Linux Kernel Anomaly Detection and Automated Process Remediation using eBPF and Machine Learning

Open-source Linux runtime framework: **eBPF kernel telemetry -> behavioural features -> anomaly detection -> (Phase-II) policy-controlled process remediation**, with overhead measured at every stage. (Phase-I) -> (Phase-II).

## Status
| Layer | Phase-I | Notes |
|---|---|---|
| `ebpf/` 3 monitors (syscalls, process lifecycle, CPU/page-faults) | done, loads & runs | tested on kernel 6.18 / x86-64 |
| `collector/` libbpf C collector | done | writes CSV + self-metrics |
| `feature_engine/` | done, 8 unit tests | window x process vectors |
| `workloads/` benign normal + anomalous generators, labeller | done | bounded, allow-listed |
| `ml/statistical` robust-z baseline + metrics | done | Isolation Forest / autoencoder = Phase-II |
| `benchmarks/overhead` | done | needs >= 5 trials on your machine |
| `remediation/`, `dashboard/`, `storage/` | **not started** (Phase-II by plan) | |

## Quick start (Ubuntu 22.04/24.04, kernel >= 5.8 with BTF)
```bash
scripts/setup.sh            # apt + pip deps, then checks the environment
scripts/build.sh            # eBPF objects, skeletons, collector
sudo mount -t tracefs nodev /sys/kernel/tracing 2>/dev/null || true
sudo scripts/run_experiment.sh train workloads/configs/normal_only.yaml 1000
sudo scripts/run_experiment.sh test                                   # default mixed plan
python3 -m ml.statistical.baseline --train datasets/features/train.csv --test datasets/features/test.csv
sudo benchmarks/overhead/run_overhead.sh 5
python3 -m pytest -q
```
Manual collection: `sudo build/ebpf-collector -o datasets/raw/local/run1 -w 1000 -d 60 [-p PID]`.

## Safety
Workloads are benign stress generators with hard caps; the runner executes only scripts under `workloads/normal|anomalous`. Phase-II remediation must act only on an explicit allow-list.

## Documents
`docs/phase1/DOCUMENT_CORRECTIONS.md` lists the errors found in the supplied package and papers. Other design docs sit beside it.
