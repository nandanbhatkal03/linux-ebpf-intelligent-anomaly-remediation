# Literature review (Phase-I)

Verification status: **V** = venue/year/DOI matched against the uploaded paper; **U** = not verifiable from uploads.

| # | Paper | Venue | Status | Takeaway used in this design |
|---|-------|-------|--------|------------------------------|
| 1 | Multi-Source eBPF Pipeline + Autoencoders | 2026 IEEE MNC (U) | text read | BCC probes (sched_switch, exec, net, privilege, fork/exit), 1 s windows, entropy features, AE/DAE/SAE (36-24-16-8). **Normal data only**; 7.17 % event loss; 17.89 pp CPU overhead. -> we aggregate in kernel, add labelled anomalies, measure loss/overhead explicitly |
| 2 | Container-Specific Service-Mesh System | IEEE TCC 14(1) 2026 (V) | text read | zero-copy eBPF syscall collection + container-specific online learning + isolation |
| 3 | eIDPS | 2025 | read | eBPF+ML network IDS/IPS; network focus |
| 4 | Cryptojacking via eBPF+ML | ICINT 2025 (V) | read | CPU/memory/network features for a resource-abuse anomaly |
| 5 | eBPF security tools (KubeArmor, Falco, Tetragon, Tracee) | IEEE Access 2025 (V) | read | mature tools = comparison points |
| 6 | Enhanced eBPF verification & runtime safety | IEEE SPW 2024 (V) | read | keep logic simple/verified; heavy logic in user space |
| 7 | Per-process/container egress filtering | ICECET 2024 (V) | read | process-aware enforcement, latency measurement method |
| 8 | Kernel packet processing with lightweight NN/DT | NoF 2023 | read | no FP in eBPF -> no NN inside the kernel |
| 9 | eBPF for 5G/6G observability | IEEE Access 2023 | **not provided (U)** | - |
| 10 | Anomaly detectors for Edge/IoT | QRS 2023 (V) | read | time-series features, detector comparison |
| 11 | eBPF: An Application Perspective | IEEE Access 2022 (V) | read | background: architecture, verifier, maps, hooks |
| 12 | ML on ADFA-LD | CONIT 2022 (V) | read | public syscall dataset (sequence-based, no timing/resource data) |
| 13 | ViperProbe | CloudNet 2020 (V) | read | per-service selective metrics; probe cost differs by class (network/scheduling expensive, disk cheap); sampling barely reduced overhead -> keep probes few and aggregate in kernel. Contains errors (see corrections) |
| 14 | Rise of eBPF for non-intrusive monitoring | NOMS 2020 | read | profiling methodology |
| 15 | Safety-critical latency with eBPF | ARCS 2019 (V) | read | bpftrace latency, tracing overhead measurement |
| 16 | AIML anomaly detection in IP networks w/ eBPF | 2023 | read | eBPF as ML feature source |
| 17 | XFAST | CNSM 2025 (DOI U) | read | in-kernel feature selection; fixed-point, tail calls; contains inconsistencies |
| 18 | In-kernel request-level metrics | ISPASS 2024 | **not provided (U)** | - |

Excluded (off-topic uploads): plant-leaf disease detection; SAR vessel detection.
