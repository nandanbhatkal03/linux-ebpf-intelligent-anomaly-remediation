# Research gap

Established: eBPF observability, eBPF security tools, syscall-sequence ML (ADFA-LD), eBPF+autoencoders on host data (Paper 1), eBPF+online learning+isolation in containers (Paper 2).

Concrete, evidence-based gaps (from the uploaded papers):
1. **No labelled evaluation** in the closest host-level work: Paper 1 reports no precision/recall/F1 and names this as future work.
2. **Benefit of source fusion unmeasured** (Paper 1 limitation) -> experiment E4 (feature groups) answers it.
3. **Collection cost is under-reported or high**: 7.17 % event loss and 17.89 pp CPU overhead (Paper 1); sampling gave little saving (Paper 13). -> in-kernel aggregation + per-program cost accounting.
4. **Detection is not connected to response** with measured cost: remediation latency, recovery time and false-action rate are not evaluated in the host-level works.
5. **Models compared on different data**: a single pipeline comparing statistical / Isolation Forest / autoencoder under identical features and overhead budget is missing.

Position: not "first eBPF anomaly detector" but a reproducible observe->analyse->decide->remediate framework with an explicit detection / latency / overhead trade-off (hypotheses H1-H4 of the package).
