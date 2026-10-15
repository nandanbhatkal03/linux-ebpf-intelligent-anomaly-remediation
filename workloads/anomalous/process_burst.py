#!/usr/bin/env python3
"""ANOMALOUS: abnormal fork/exec rate. Short-lived children are spawned
SEQUENTIALLY at a fixed rate (never accumulating -> not a fork bomb), with a
hard cap on the total number of children."""
import os, subprocess, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from workloads.common import parse_args, level, deadline

MAX_CHILDREN = 20000


def main():
    a = parse_args(__doc__)
    rate = level(a.intensity, 20, 80, 200)        # children per second (upper bound)
    end, n, gap = deadline(a.duration), 0, 1.0 / rate
    while time.monotonic() < end and n < MAX_CHILDREN:
        t = time.monotonic()
        subprocess.run(["/bin/true"], check=False)
        n += 1
        time.sleep(max(0.0, gap - (time.monotonic() - t)))


if __name__ == "__main__":
    main()
