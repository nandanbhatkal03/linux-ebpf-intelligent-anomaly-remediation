#!/usr/bin/env bash
# Experiment E1/E2: monitoring overhead of eBPF configurations vs baselines.
#   sudo benchmarks/overhead/run_overhead.sh [trials=5] [out_csv]
# Each trial runs three micro-benchmarks (sys, io, cpu) while a monitor is active.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TRIALS="${1:-5}"
OUT="${2:-$ROOT/benchmarks/results/raw/overhead_$(date +%Y%m%d_%H%M%S).csv}"
COLL="$ROOT/build/ebpf-collector"
BENCH="$ROOT/build/syscall_bench"
SYS_N="${SYS_N:-3000000}"; IO_N="${IO_N:-1000000}"; CPU_N="${CPU_N:-1500}"
mkdir -p "$(dirname "$OUT")" "$ROOT/build"
[[ -x "$COLL" ]] || { echo "build first: scripts/build.sh"; exit 1; }
cc -O2 -o "$BENCH" "$ROOT/benchmarks/syscall/syscall_bench.c"

echo "config,trial,metric,value" > "$OUT"
MON_PID=""
start_mon() {   # $1=config
  case "$1" in
    baseline) ;;
    proc_polling) python3 "$ROOT/benchmarks/overhead/proc_poller.py" 0.1 & MON_PID=$! ;;
    ebpf_syscall) "$COLL" -o /tmp/ovh_$$ -w 1000 --no-process --no-resource 2>/dev/null & MON_PID=$! ;;
    ebpf_process_resource) "$COLL" -o /tmp/ovh_$$ -w 1000 --no-syscalls 2>/dev/null & MON_PID=$! ;;
    ebpf_full) "$COLL" -o /tmp/ovh_$$ -w 1000 2>/dev/null & MON_PID=$! ;;
  esac
  [[ -n "$MON_PID" ]] && sleep 1.5 || true
}
stop_mon() {
  [[ -n "$MON_PID" ]] || return 0
  kill -INT "$MON_PID" 2>/dev/null || true
  for _ in $(seq 50); do kill -0 "$MON_PID" 2>/dev/null || break; sleep 0.1; done
  kill -KILL "$MON_PID" 2>/dev/null || true          # escalate if SIGINT was ignored
  wait "$MON_PID" 2>/dev/null || true; MON_PID=""
}
trap stop_mon EXIT

CONFIGS="baseline proc_polling ebpf_syscall ebpf_process_resource ebpf_full"
for ((t=1; t<=TRIALS; t++)); do
  for cfg in $CONFIGS; do            # interleaved to spread drift across configs
    start_mon "$cfg"
    echo "$cfg,$t,sys_ns_per_call,$("$BENCH" sys "$SYS_N")" >> "$OUT"
    echo "$cfg,$t,io_ns_per_read,$("$BENCH" io "$IO_N")"   >> "$OUT"
    echo "$cfg,$t,cpu_seconds,$("$BENCH" cpu "$CPU_N")"    >> "$OUT"
    stop_mon
    echo "trial $t/$TRIALS  $cfg done" >&2
  done
done
echo "raw results: $OUT" >&2
python3 "$ROOT/benchmarks/overhead/summarize.py" "$OUT"
