#!/usr/bin/env bash
# sudo scripts/start_monitor.sh <outdir> [collector args...]   (foreground; Ctrl-C to stop)
mount | grep -q tracefs || mount -t tracefs nodev /sys/kernel/tracing 2>/dev/null || true
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:?usage: start_monitor.sh <outdir> [args]}"; shift
exec "$ROOT/build/ebpf-collector" -o "$OUT" "$@"
