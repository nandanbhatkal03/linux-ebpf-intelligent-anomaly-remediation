# Low-Level Design

## eBPF programs (`ebpf/programs/`)
| Program | Hook | Output | Notes |
|---------|------|--------|-------|
| `syscall_monitor.bpf.c` | `tp_btf/sys_enter` | `LRU_PERCPU_HASH syscall_counts[(tgid,nr)] -> {count, comm}` | per-CPU: no atomics; LRU: bounded under pid churn |
| `process_monitor.bpf.c` | `tp_btf/sched_process_fork`, `tracepoint/sched/sched_process_exec`, `sched_process_exit` | ring buffer of 56-byte `struct event` | threads ignored on fork; exit reported once per process; children inherit monitoring |
| `resource_monitor.bpf.c` | `tp_btf/sched_switch`, `exceptions/page_fault_user` (optional) | `LRU_PERCPU_HASH cpu_stats[tgid]` = on-CPU ns, switches, involuntary switches, page faults | on-CPU time = delta since previous switch on that CPU, charged to `prev` |

Shared (`event_maps.h`): `targets` set, per-CPU `stats` (ring-buffer drops, map failures), `self_tgid` (collector never traces itself), `filter_enabled`.

## Wire format (`event_types.h`)
`struct event { u64 timestamp; u64 value; u32 pid, ppid, uid, gid, event_type, _pad; char comm[16]; }` = 56 B.
`value`: fork -> child tgid; exec -> tid that exec'd; exit -> raw `exit_code`.

## Collector (`collector/src/`)
`loader.c` (open/configure/load/attach, `bpf_enable_stats(RUN_TIME)`), `ring_buffer.c` + `event_decoder.c`, `map_flush.c` (key snapshot -> `lookup_and_delete`, sums per-CPU slots), `metrics.c` (CPU ms, RSS, drops per window), `main.c` (CLI, window loop, outputs). Output schema: see `datasets/README.md`.

## Feature engine (`feature_engine/src/`)
`event_parser` -> `windowing.build_features`: window index = midpoint of collector window; outer-merge syscall/resource/process features; `temporal_features` adds `*_rmean, *_rstd, *_burst (Goh-Barabasi), *_delta` from the **previous** `history` windows. Features: sys_total/unique/entropy/rate, category counts+fractions (config-driven), cpu_util, switches, invol_ratio, page_faults, n_fork/exec/exit.

## Detection (P1 baseline)
Robust z: `z_j = |x_j - median_j| / (1.4826 MAD_j)` (std fallback); score = mean of top-k z; threshold = q-quantile of **normal** training scores.

## Metrics
Accuracy, precision, recall, F1, FPR, FNR, ROC-AUC (`ml/evaluation/metrics.py`); overhead: ns/syscall, ns/read, CPU seconds vs baseline, per-program `run_time_ns/run_cnt`, drops.
