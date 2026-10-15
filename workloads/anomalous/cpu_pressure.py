#!/usr/bin/env python3
"""ANOMALOUS: sustained 100 % CPU spin (no sleeping) in 1-2 bounded processes."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from workloads.common import parse_args, level, deadline


def spin(end):
    x = 0
    while time.monotonic() < end:
        x = (x * 31 + 7) % 1000003


def main():
    a = parse_args(__doc__)
    end = deadline(a.duration)
    workers = min(level(a.intensity, 1, 1, 2), max(1, os.cpu_count() or 1))
    kids = []
    for _ in range(workers - 1):
        pid = os.fork()
        if pid == 0:
            spin(end); os._exit(0)
        kids.append(pid)
    spin(end)
    for k in kids:
        os.waitpid(k, 0)


if __name__ == "__main__":
    main()
