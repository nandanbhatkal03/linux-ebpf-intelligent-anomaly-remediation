#!/usr/bin/env bash
# All Phase-II live experiments (needs root + trained models). ~20 min on a small VM.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
mount | grep -q tracefs || mount -t tracefs nodev /sys/kernel/tracing 2>/dev/null || true
M=${MODEL:-ml/models/autoencoder.joblib}
for SC in runaway_cpu cpu_pressure process_burst; do python3 -m experiments.live_remediation --model $M --scenario $SC --anomaly-s 40 --duration 60; done
python3 -m experiments.false_actions --model $M --duration 90
python3 -m experiments.scalability --model $M --counts 1 5 10 25 --seconds 20
python3 -m experiments.window_study --train-runs datasets/raw/local/train_* --test-runs datasets/raw/local/test_* --sizes 500 1000 2000 5000
SYS_N=1000000 IO_N=300000 CPU_N=300 benchmarks/overhead/run_overhead.sh 3 benchmarks/results/raw/overhead_phase2.csv
echo EXPERIMENTS_DONE
