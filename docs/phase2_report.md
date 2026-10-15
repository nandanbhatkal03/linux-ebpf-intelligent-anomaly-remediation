# Phase-II results (measured; reproduce with `scripts/run_all_phase2.sh`)

**Setup and limits.** 1-vCPU VM, kernel 6.18, x86-64, one dataset: 5 normal runs (1,170 normal windows), 6 held-out test runs, 5 anomaly types x 6 instances (330 anomalous windows), 1 s feature windows. Small sample: no confidence intervals; treat differences of a few points as noise. Anomalies are benign synthetic stress workloads, not real attacks.

## 1. Detection (E3) - threshold chosen on test runs 0-2, reported on runs 3-5
| Model | ROC-AUC | F1 | Recall | FPR | Instances detected | Persistent false alarms | Inference |
|---|---|---|---|---|---|---|---|
| Statistical (robust z) | 0.974 | 0.857 | 0.873 | 3.1 % | 87 % | 3 | 0.7 us/window |
| Isolation Forest | 0.958 | 0.771 | 0.703 | 2.3 % | 87 % | 0 | 14.5 us |
| Autoencoder | 0.958 | 0.764 | 0.921 | 9.3 % | 100 % | 17 | 2.1 us |

Median detection latency about 1.9 s (two consecutive 1 s windows). At the naive 99th-percentile threshold (`model_comparison.csv`) the Isolation Forest drops to F1 0.30: **the threshold matters as much as the model**. The statistical baseline is the best F1 here; the ML models are not shown to beat it on this data.
Where false positives come from: for the statistical model and the Isolation Forest almost all lie in the first 3 s / last 2 s of a process (start-up and shutdown transients; steady-state FPR about 0), hence the 3 s warm-up in the policy. The autoencoder's false positives are spread over steady-state windows.

## 2. Feature groups (E4, Isolation Forest, q = 0.9, all 6 test runs - not a held-out split)
| Feature set | n | ROC-AUC | F1 | Recall | FPR |
|---|---|---|---|---|---|
| all | 32 | 0.960 | 0.767 | 0.697 | 0.023 |
| only syscall | 10 | 0.952 | 0.843 | 0.924 | 0.051 |
| without syscall | 22 | 0.936 | 0.643 | 0.552 | 0.031 |
| only resource | 3 | 0.890 | 0.713 | 0.806 | 0.086 |
| without resource | 29 | 0.956 | 0.755 | 0.673 | 0.021 |
| without process | 31 | 0.962 | 0.717 | 0.633 | 0.025 |
| only temporal | 17 | 0.908 | 0.507 | 0.467 | 0.070 |
| without temporal | 15 | 0.955 | 0.817 | 0.924 | 0.064 |
Syscall features carry most of the signal; the temporal features did not help here.

## 3. Window size (E5, Isolation Forest at the naive q = 0.99 operating point)
| Window | ROC-AUC | F1 | Event recall | Median latency |
|---|---|---|---|---|
| 0.5 s | 0.936 | 0.21 | 23 % | 1.9 s |
| 1 s | 0.960 | 0.30 | 27 % | 3.4 s |
| 2 s | 0.990 | 0.68 | 87 % | 2.9 s |
| 5 s | 0.976 | 0.71 | 93 % | 9.9 s |
Longer windows detect more but later; the low absolute scores at 0.5-1 s reflect the conservative threshold, not only the window.

## 4. Monitoring overhead (E1/E2, 3 trials, micro-benchmarks, 1 vCPU)
| Config | getppid ns/call | overhead | 4 KiB read ns | overhead | CPU-bound loop |
|---|---|---|---|---|---|
| baseline | 122 | - | ~195 | - | - |
| /proc polling 10 Hz | 127 | +4 % | 203 | +4 % | +4.7 % |
| eBPF process+resource | 128 | +5 % | 207 | +6 % | +1.9 % |
| eBPF syscall counter | 223 | +83 % | 302 | +55 % | +2.1 % |
| eBPF full | 212 | +74 % | 296 | +52 % | -0.4 % (noise) |
| strace -f | 7,687 | +6,200 % | 9,488 | +4,772 % | +1.4 % |
A `sys_enter` probe costs about 90-100 ns per syscall, a worst case (loop of nothing but syscalls). It is roughly 70x cheaper than strace and invisible to compute-bound work. The std. dev. at n = 3 is up to 10 %.

## 5. Scalability (E9, PID-scoped collector + live detector, 20 s each)
| Processes | Collector CPU | Ring-buffer drops | Detector ms / 1 s window |
|---|---|---|---|
| 1 | 0.64 % | 0 | 86 |
| 5 | 0.62 % | 0 | 174 |
| 10 | 0.64 % | 0 | 273 |
| 25 | 0.62 % | 0 | 734 |
The collector is flat; the Python detector is the bottleneck (about 29 ms per scored row) and would fall behind near 35 processes on this machine. Vectorising the feature build is the next optimisation. (A fork storm initially made the detector lag minutes behind because it built features for unscored children; fixed by filtering to registered targets first.)

## 6. Live remediation (E7/E8, autoencoder, observe-only vs active)
| Scenario | Detect | First action latency | Anomaly lifetime observe -> active | Victim throughput during anomaly (observe -> active; normal about 800-1,050 loops/s) |
|---|---|---|---|---|
| cpu_pressure | 6.8 s | 8-12 ms | 40.2 s -> 13.0 s | 25 -> 603 |
| process_burst | 6.6 s | 5-9 ms | 40.5 s -> 13.0 s | 610 -> 602 (this anomaly barely hurts the victim) |
| runaway_cpu | 2.8 s after onset | 5-8 ms | 30.1 s -> 3.9 s | 52 -> 1,527, **confounded**: a false alert + restrict fired 2.4 s before onset in the active arm |
Detect time includes the 3 s warm-up and 2-window persistence. The ladder walked restrict -> suspend -> terminate.

## 7. Safety
Normal-only run, 90 s, 3 supervised workloads, 267 scored windows: **0 alerts, 0 restricts, 0 suspends, 0 terminates**. Unit tests show unregistered processes, PID-reused processes, pid 1, self, and dry-run targets are never touched; every attempt (including blocked ones) is audited.

## 8. Threats to validity / open items
Synthetic workloads on one VM; autoencoder false positives (9-11 % window FPR) mean its live use relies on persistence + reversible-first actions; threshold selected on only 3 validation runs; PID reuse is not handled in the feature pipeline (the action path guards it with start times); block-I/O and network probes are not implemented; Isolation Forest/statistical scores rarely reach T2, so live critical escalation was only exercised with the autoencoder.
