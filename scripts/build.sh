#!/usr/bin/env bash
# Builds eBPF objects + skeletons, the collector and the micro-benchmark.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/scripts/gen_syscall_table.py"
make -C "$ROOT/ebpf"
make -C "$ROOT/collector"
cc -O2 -o "$ROOT/build/syscall_bench" "$ROOT/benchmarks/syscall/syscall_bench.c"
echo "built: $ROOT/build/ebpf-collector"
