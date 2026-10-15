# Datasets
Raw collector output per run in `raw/local/<run_id>/` (all times CLOCK_MONOTONIC ns):
* `process_events.csv`: ts_ns,event(fork|exec|exit),pid,ppid,uid,gid,value,comm
* `syscall_windows.csv`: window_start_ns,window_end_ns,pid,comm,nr,count
* `resource_windows.csv`: ...,pid,comm,cpu_ns,switches,invol_switches,page_faults
* `collector_metrics.csv`: per-window collector CPU ms, RSS, events received, ring-buffer drops, map failures
* `bpf_prog_stats.csv`: run_cnt, run_time_ns per BPF program; `meta.json`: kernel, window, clock origin
`labels/<run>_labels.csv`: ground truth from `workloads/run_workloads.py`. `features/<run>.csv`: model input (`label`: 1 anomalous, 0 normal, -1 unlabelled/excluded).
Public data: ADFA-LD (syscall sequences only; cannot supply resource features). Do not commit raw data.
