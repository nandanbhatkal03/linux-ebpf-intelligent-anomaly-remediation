# Corrections to the supplied documents

Every item was checked against the files you uploaded. "Fixed" = corrected in this repository; "Flag" = I could not
verify it offline or it needs your decision.

## A. MCSP34 Phase-I Project Package (v2)

| # | Problem | Where | Resolution |
|---|---------|-------|-----------|
| A1 | Section numbers collide: two sections numbered **17** (Folder Structure and SRS), two numbered **49**; there is no 16; sub-sections are numbered under the wrong parent (16.1-16.5 under 17, SRS 16.1-16.3 under 17, 20.1 under 21, 22.1 under 23, 24.1 under 25). Cross-references such as "Section 16.4" are ambiguous. | §15-§25, §49 | Fixed. `docs/phase1/` uses one continuous numbering. |
| A2 | **FR-15** says the system "shall provide a dashboard", but §16.2 and §49 say the dashboard must stay optional and must not be started in Phase-I. | FR-15 | Fixed: FR-15 is "should", Phase-II, outside the core pipeline (`srs.md`). |
| A3 | **Kernel requirement missing.** The design relies on BPF ring buffers, which need Linux **>= 5.8**, and on BTF/CO-RE (`/sys/kernel/btf/vmlinux`). "A stable Ubuntu LTS kernel" does not guarantee either (Ubuntu 20.04's GA kernel is 5.4). The optional LSM hooks need >= 5.7, `CONFIG_BPF_LSM` and `lsm=bpf` on the kernel command line. | NFR-10, §10, §40 | Fixed: NFR-10 now states kernel >= 5.8 + BTF (Ubuntu 22.04/24.04); `scripts/check_environment.sh` verifies it. |
| A4 | **Event structure** (§15.2) uses userspace types (`uint64_t`) inside a kernel program and has implicit padding between `event_type` and the 8-byte `value`; `value` has no defined meaning. | §15.2 | Fixed in `ebpf/include/event_types.h`: `__u64/__u32`, explicit `_pad`, 56-byte size, `value` semantics defined per event type. |
| A5 | **Design risk.** The pipeline implies one event per syscall through the ring buffer. The closest related paper (Paper 1) measured **7.17 % event loss** (154,503 events lost; 2,000,774 processed) and **17.89 +/- 9.64 pp** CPU overhead with per-event perf buffers; the package never states those limits. | §5, §10, Paper 1 entry | Fixed by design: syscalls are **counted in-kernel** per (tgid, syscall) and drained once per window; only sparse fork/exec/exit events use the ring buffer. Loss is still measured (`collector_metrics.csv`). |
| A6 | Paper 1 entry omits that the paper evaluated **only normal traffic** (no precision/recall/F1, no labelled anomalies) and did not measure the benefit of source fusion. These are exactly the gaps your project fills, so they belong in the gap analysis. | Paper 1, §25 | Fixed in `research_gap.md`. |
| A7 | Features are keyed by "PID". PIDs are recycled and threads share a tgid. | §11 | Partly fixed: probes use **tgid**. PID reuse inside one run is not handled yet (Flag: Phase-II should key on `(tgid, start_time)`). |
| A8 | Overhead metric `CPU_with - CPU_without` is under-specified: per-process CPU percentages are per-core, so they must be normalised by the CPU count (Paper 1 does this). | §23.2 | Fixed in `lld.md` / benchmark scripts (ns-per-syscall and wall-time deltas, plus in-kernel `run_time_ns` per BPF program). |
| A9 | Two of the 18 listed papers are **not in your upload**: Paper 9 (IEEE Access 2023, 5G/6G eBPF) and Paper 18 (ISPASS 2024). | §27 | Flag: their DOIs/claims are unverified here. Two uploaded files are **not in the package at all and are off-topic**: *Disease Detection of Plant Leaf* and *Nearshore Vessel Detection in SAR Imagery*. They were not used; remove them from the reading set. |
| A10 | Venue/DOI for Paper 1 (2026 IEEE MNC), Paper 2's DOI and Paper 17's DOI do not appear in the uploaded text. | §27 | Flag: confirm on IEEE Xplore before citing. Venue/year/DOI of Papers 4-7, 10-12, 14-15 **do** match the uploaded files. |
| A11 | Stage 2 lists `strace` as a baseline but no experiment compares against it; H1 speaks of "user-space tracing". | §10, §22, H1 | Flag: `run_overhead.sh` currently compares against `/proc` polling only; add an `strace -f -c` configuration for E1 before claiming H1. |

## B. ViperProbe (CloudNet 2020) - errors inside the paper

| # | Problem | Resolution |
|---|---------|-----------|
| B1 | Acknowledgments contain a copy-paste/search artefact: "We thank **Showing results for** Rodrigo Fonseca". | Cite as "thank Rodrigo Fonseca"; do not quote the sentence. |
| B2 | Text: ViperProbe "allocates **over 200 % more pods**" for the recommendation service. Table II: 13 vs 5 pods = **+160 %** (2.6x). | Use 160 % / 2.6x. |
| B3 | Text: "fewer replicas in **all** services except recommendation". Table II: Cart Service is 1 vs 1 (equal). | "fewer or equal". |
| B4 | Typos "eBFP", "Berkley"; "Linux Kernel 3.15+ and 4.15+" is imprecise (see C1). | Cosmetic. |

## C. XFAST (CNSM 2025) - errors inside the paper

| # | Problem | Resolution |
|---|---------|-----------|
| C1 | "eBPF ... introduced in version **3.15**". The internal eBPF VM landed in 3.15, but the user-visible `bpf()` syscall (what makes it usable) arrived in **3.18**. (XDP in 4.8 is correct.) | Use "3.18" for user-space eBPF. Same applies to ViperProbe's "3.15+". |
| C2 | GA cost is described inconsistently: "one generation of individuals is evaluated per packet" vs "each packet triggers only one step of one GA stage" vs completion needs ">= 3 x generations" packets. With population 32 and 300 generations, per-individual steps would need ~28,800 packets, but each 60 s replay carries ~12,840 (214 pkt/s). | Flag: ambiguous; read the released code before reusing the claim. |
| C3 | Text says CPU "remained below 5 % of a single core", but Fig. 8's baseline is 7.88 +/- 3.94 % with bars near 10-12 %. | Flag: trust the figure/data, not the sentence. |
| C4 | The GA fitness uses hit counts derived from Isolation-Forest thresholds trained on the same dataset that the F1 (0.80 -> 0.85) is computed on: possible circularity, single run, no variance. | Cite the result as indicative only. |

## D. What the build changed on purpose (not errors)

* Syscalls: in-kernel aggregation (A5). Resource monitor charges exact on-CPU time per `sched_switch`.
* Detection unit: **(window, tgid)** rows; labelling default `scope=root` because a fork storm is visible at the parent (`n_fork`), while each short-lived child looks normal on its own (observed in the first end-to-end run: 399 mislabelled child rows, recall 1.5 % for `process_burst`).
