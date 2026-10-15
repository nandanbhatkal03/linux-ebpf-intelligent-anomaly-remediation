#!/usr/bin/env python3
"""ANOMALOUS (behaviour change): behaves like the normal duty-cycled cpu_workload for --after seconds, then
turns into a 100 % CPU spin (a runaway loop in a long-running service). Bounded by --duration."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from workloads.common import parse_args, deadline


def main():
    def extra(ap):
        ap.add_argument("--after", type=float, default=10.0)
    a = parse_args(__doc__, extra)
    end, turn = deadline(a.duration), time.monotonic() + a.after
    x, period, duty = 0, 0.1, 0.30
    while time.monotonic() < end:
        if time.monotonic() >= turn:
            x = (x * 31 + 7) % 1000003           # spin, no sleeping
            continue
        t = time.monotonic()
        while time.monotonic() - t < duty * period:
            x = (x * 31 + 7) % 1000003
        time.sleep(period * (1 - duty))


if __name__ == "__main__":
    main()
