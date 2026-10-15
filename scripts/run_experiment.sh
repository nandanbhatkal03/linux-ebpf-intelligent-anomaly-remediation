#!/usr/bin/env bash
# One labelled run: collector + workload plan -> raw data -> labelled features.
#   sudo scripts/run_experiment.sh <run_id> [plan.yaml] [window_ms]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="${1:?usage: run_experiment.sh <run_id> [plan.yaml] [window_ms]}"
PLAN="${2:-$ROOT/workloads/configs/workload_config.yaml}"
WIN="${3:-1000}"
RAW="$ROOT/datasets/raw/local/$RUN"; LAB="$ROOT/datasets/labels/${RUN}_labels.csv"
FEAT="$ROOT/datasets/features/${RUN}.csv"
rm -rf "$RAW" "$LAB"; mkdir -p "$RAW"

"$ROOT/build/ebpf-collector" -o "$RAW" -w "$WIN" --run-id "$RUN" 2> "$RAW/collector.log" &
COLL=$!
trap 'kill -INT $COLL 2>/dev/null || true' EXIT
for _ in $(seq 50); do grep -q "collector running" "$RAW/collector.log" 2>/dev/null && break; sleep 0.1; done
kill -0 $COLL 2>/dev/null || { cat "$RAW/collector.log" >&2; echo "collector failed to start (is tracefs mounted? sudo mount -t tracefs nodev /sys/kernel/tracing)" >&2; exit 1; }
sleep 1                                           # let a clean baseline window pass
python3 "$ROOT/workloads/run_workloads.py" --plan "$PLAN" --run-id "$RUN" --labels "$LAB"
sleep 1
kill -INT $COLL; wait $COLL || true; trap - EXIT
cat "$RAW/collector.log" >&2
cd "$ROOT"
python3 -m feature_engine.src.build_features "$RAW" -o "$FEAT" --window-ms "$WIN" --labels "$LAB"
