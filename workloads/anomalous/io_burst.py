#!/usr/bin/env python3
"""ANOMALOUS: high-frequency small file operations (create/stat/open/read/
unlink) over a few hundred files in a private temp dir."""
import os, shutil, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from workloads.common import parse_args, level, deadline, workdir


def main():
    a = parse_args(__doc__)
    nfiles = level(a.intensity, 50, 200, 400)
    d = workdir("io_burst")
    end = deadline(a.duration)
    try:
        for i in range(nfiles):
            with open(os.path.join(d, "f%d" % i), "w") as f:
                f.write("x")
        while time.monotonic() < end:
            for i in range(nfiles):
                p = os.path.join(d, "f%d" % i)
                os.stat(p)
                with open(p, "rb") as f:
                    f.read(1)
            if a.intensity != "high":
                time.sleep(0.005)
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
