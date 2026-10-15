#!/usr/bin/env bash
# Reproduce everything for Phase II (needs root): collect -> features -> train -> operating point -> evaluate -> live experiments.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
mount | grep -q tracefs || mount -t tracefs nodev /sys/kernel/tracing 2>/dev/null || true
scripts/build.sh >/dev/null
[[ "${SKIP_COLLECT:-0}" == 1 ]] || scripts/collect_dataset.sh
for r in datasets/raw/local/*; do n=$(basename $r)
  python3 -m feature_engine.src.build_features $r -o datasets/features/$n.csv --window-ms 1000 --labels datasets/labels/${n}_labels.csv | tail -1; done
python3 -m ml.train datasets/features/train_*.csv --out ml/models
python3 -m ml.operating_point --train datasets/features/train_*.csv --test datasets/features/test_*.csv
python3 -m ml.evaluate --train datasets/features/train_*.csv --test datasets/features/test_*.csv --out results/phase2
scripts/run_phase2_experiments.sh
echo ALL_DONE
