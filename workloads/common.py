"""Shared helpers for the controlled workload generators.

SAFETY: these are *benign stress generators*, not malware. Every one is
bounded by duration, memory and process-count caps and touches only its own
temporary directory."""
import argparse
import os
import tempfile
import time

MAX_DURATION_S = 600
INTENSITIES = ("low", "medium", "high")


def parse_args(desc, extra=None):
    ap = argparse.ArgumentParser(description=desc)
    ap.add_argument("--duration", type=float, default=10.0, help="seconds (hard cap %d)" % MAX_DURATION_S)
    ap.add_argument("--intensity", choices=INTENSITIES, default="medium")
    if extra:
        extra(ap)
    a = ap.parse_args()
    a.duration = max(0.1, min(a.duration, MAX_DURATION_S))
    return a


def level(intensity, low, medium, high):
    return {"low": low, "medium": medium, "high": high}[intensity]


def deadline(duration):
    return time.monotonic() + duration


def mem_available_mb():
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 512


def workdir(prefix):
    return tempfile.mkdtemp(prefix=prefix + "_", dir=os.environ.get("WORKLOAD_TMP", None))
