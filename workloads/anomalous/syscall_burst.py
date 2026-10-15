#!/usr/bin/env python3
"""ANOMALOUS: unusual syscall distribution - a tight loop dominated by a few
cheap syscalls (getppid/getpriority/times/uname) with no useful work."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from workloads.common import parse_args, level, deadline


def main():
    a = parse_args(__doc__)
    batch = level(a.intensity, 2000, 20000, 100000)
    sleep = level(a.intensity, 0.05, 0.01, 0.0)
    end = deadline(a.duration)
    while time.monotonic() < end:
        for _ in range(batch):
            os.getppid(); os.getpriority(os.PRIO_PROCESS, 0)
        os.times(); os.uname()
        if sleep:
            time.sleep(sleep)


if __name__ == "__main__":
    main()
