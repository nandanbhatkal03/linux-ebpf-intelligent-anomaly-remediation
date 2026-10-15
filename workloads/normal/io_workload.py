#!/usr/bin/env python3
"""NORMAL: paced file writes/reads with occasional fsync in a private temp dir."""
import os, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from workloads.common import parse_args, level, deadline, workdir


def main():
    a = parse_args(__doc__)
    chunk = level(a.intensity, 4, 32, 128) * 1024
    pause = level(a.intensity, 0.10, 0.05, 0.02)
    d = workdir("io_normal")
    path, end, n = os.path.join(d, "data.bin"), deadline(a.duration), 0
    try:
        while time.monotonic() < end:
            with open(path, "ab") as f:
                f.write(os.urandom(chunk))
                if n % 10 == 0:
                    f.flush(); os.fsync(f.fileno())
            if os.path.getsize(path) > 8 * 1024 * 1024:
                os.truncate(path, 0)
            with open(path, "rb") as f:
                f.read(chunk)
            n += 1
            time.sleep(pause)
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
