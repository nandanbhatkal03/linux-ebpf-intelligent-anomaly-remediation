#!/usr/bin/env bash
# Removes build output and generated data (keeps sources). Pass --data to also wipe datasets/results.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
pkill -INT -x ebpf-collector 2>/dev/null || true
rm -rf "$ROOT/build" "$ROOT/ebpf/headers/vmlinux.h"
if [[ "${1:-}" == "--data" ]]; then
  rm -rf "$ROOT"/datasets/raw/local/* "$ROOT"/datasets/features/* "$ROOT"/datasets/labels/* "$ROOT"/benchmarks/results/raw/* "$ROOT"/benchmarks/results/processed/*
fi
echo "clean"
