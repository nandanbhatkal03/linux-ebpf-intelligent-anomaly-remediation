#!/usr/bin/env python3
"""Conventional baseline: poll /proc for every process (what ps/top do)."""
import os, sys, time

period = float(sys.argv[1]) if len(sys.argv) > 1 else 0.1
while True:
    for pid in os.listdir("/proc"):
        if pid.isdigit():
            try:
                with open(f"/proc/{pid}/stat") as f:
                    f.read()
                with open(f"/proc/{pid}/status") as f:
                    f.read()
            except OSError:
                pass
    time.sleep(period)
