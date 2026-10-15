#!/usr/bin/env python3
"""NORMAL 'victim' application used to measure the IMPACT of an anomaly and of remediation.
Nice-19 batch job: repeatedly does a fixed chunk of work (no sleeping). Once per second it logs the completed loop count
(`samples` = THROUGHPUT) and the p95 wake-up delay. CPU contention lowers throughput; remediation restores it."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from workloads.common import parse_args


def main():
    def extra(ap):
        ap.add_argument("--log", default="/tmp/latency_probe.csv")
    a = parse_args(__doc__, extra)
    os.nice(19)          # lowest priority: it only gets CPU the monitored workloads leave idle
    delays, t_end = [], time.monotonic() + a.duration
    next_log = time.monotonic() + 1.0
    with open(a.log, "w") as f:
        f.write("t_mono_ns,p95_delay_ms,max_delay_ms,samples\n")
        while time.monotonic() < t_end:
            t = time.monotonic()
            delays.append((time.monotonic() - t) * 1000)
            x = 0
            for _ in range(20000):
                x += 1
            if time.monotonic() >= next_log:
                delays.sort()
                f.write(f"{time.monotonic_ns()},{delays[int(0.95 * (len(delays) - 1))]:.3f},{delays[-1]:.3f},{len(delays)}\n")
                f.flush()
                delays, next_log = [], next_log + 1.0


if __name__ == "__main__":
    main()
