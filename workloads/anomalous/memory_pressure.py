#!/usr/bin/env python3
"""ANOMALOUS: steadily growing, continuously touched allocation (leak-like),
capped at 40 % of currently available memory."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from workloads.common import parse_args, level, deadline, mem_available_mb


def main():
    a = parse_args(__doc__)
    cap_mb = min(level(a.intensity, 128, 384, 768), int(mem_available_mb() * 0.4))
    step_mb = level(a.intensity, 4, 8, 16)
    end, blocks = deadline(a.duration), []
    while time.monotonic() < end:
        if len(blocks) * step_mb < cap_mb:
            b = bytearray(step_mb * 1024 * 1024)
            for i in range(0, len(b), 4096):
                b[i] = 1
            blocks.append(b)
        time.sleep(0.05)


if __name__ == "__main__":
    main()
