#!/usr/bin/env python3
"""NORMAL: duty-cycled CPU computation (busy a fraction of each 100 ms period)."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from workloads.common import parse_args, level, deadline


def main():
    a = parse_args(__doc__)
    duty = level(a.intensity, 0.10, 0.30, 0.60)
    period, end = 0.1, deadline(a.duration)
    x = 0
    while time.monotonic() < end:
        t = time.monotonic()
        while time.monotonic() - t < duty * period:
            x = (x * 31 + 7) % 1000003
        time.sleep(max(0.0, period * (1 - duty)))


if __name__ == "__main__":
    main()
