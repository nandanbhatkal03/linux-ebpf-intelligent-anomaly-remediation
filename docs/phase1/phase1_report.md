# Phase-I report - preliminary results (template + numbers measured during the build)

> These numbers come from a **1-vCPU Firecracker VM, kernel 6.18, 2 trials**. They prove the pipeline runs; they are NOT thesis results. Re-run on your 4+ core Ubuntu machine with >= 5 trials (`benchmarks/overhead/run_overhead.sh 5`).

## 9.1 Prototype
Three monitors, six BPF programs, verified and loaded on kernel 6.18; PID filter with descendant inheritance verified (descendants of a filtered shell appeared, unrelated processes did not).

## 9.3 Initial overhead (micro-benchmarks, mean of 2 trials)
| Config | getppid() ns/call | overhead | 4 KiB read ns | overhead | CPU-bound loop |
|---|---|---|---|---|---|
| baseline | 280.5 | - | 497.3 | - | 0 % |
| /proc polling (10 Hz) | 289.6 | +3.2 % | 504.7 | +1.5 % | +2.1 % |
| eBPF syscall counter | 384.6 | +37 % | 587.6 | +18 % | +0.4 % |
| eBPF process+resource | 277.3 | -1 % (noise) | 506.3 | +1.8 % | -0.7 % |
| eBPF full | 380.2 | +36 % | 573.3 | +15 % | -1.8 % (noise) |

Reading: the `sys_enter` probe costs ~100 ns per syscall (in-kernel average 56 ns/run in the smoke test). That is a *worst case* (a loop of nothing but syscalls); a CPU-bound workload shows no measurable cost. Process/scheduler probes are cheap. Std. dev. at n=2 is large; do not quote percentages.

## Labelled pipeline smoke test
Normal-only training run -> mixed test run (cpu_pressure, process_burst, syscall_burst): ROC-AUC 0.93, FPR 2 %, recall 39 % at a 99th-percentile threshold, **78 training windows** only. syscall_burst recall 100 %, cpu_pressure 17 %, process_burst 0 %. Too little data to conclude anything; this is the baseline Phase-II models must beat after proper data collection (>= 30 min of normal activity per the related work's protocol, repeated runs, held-out workloads).

## Known limitations
PID reuse not handled; page-fault probe needs the `exceptions:page_fault_user` tracepoint; block-I/O probe not implemented; no `strace` baseline yet; single-architecture testing (x86-64).
