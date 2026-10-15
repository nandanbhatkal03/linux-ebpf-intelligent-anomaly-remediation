#!/usr/bin/env python3
"""NORMAL: allocates a bounded working set once and re-touches it slowly."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from workloads.common import parse_args, level, deadline, mem_available_mb


def main():
    a = parse_args(__doc__)
    mb = min(level(a.intensity, 16, 64, 128), mem_available_mb() // 4)
    buf = bytearray(mb * 1024 * 1024)
    for i in range(0, len(buf), 4096):          # touch every page once
        buf[i] = 1
    end, i = deadline(a.duration), 0
    while time.monotonic() < end:
        for _ in range(256):                     # light, steady re-touching
            buf[(i * 4096) % len(buf)] ^= 1
            i += 1
        time.sleep(0.05)


if __name__ == "__main__":
    main()
