#!/usr/bin/env bash
# Collect the Phase-II dataset (needs root). ~20 minutes. Raw runs land in datasets/raw/local/{train,test}_N.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
python3 scripts/gen_plans.py >/dev/null
WIN="${WIN:-500}"
for k in 0 1 2 3 4; do scripts/run_experiment.sh train_$k workloads/configs/generated/train_$k.yaml $WIN 2>&1 | tail -1; done
for k in 0 1 2 3 4 5; do scripts/run_experiment.sh test_$k workloads/configs/generated/test_$k.yaml $WIN 2>&1 | tail -1; done
echo COLLECTION_DONE
