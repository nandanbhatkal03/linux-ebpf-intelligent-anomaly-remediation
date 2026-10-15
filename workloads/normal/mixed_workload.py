#!/usr/bin/env python3
"""NORMAL: shell-like mix of compute, file I/O and a few short child processes."""
import os, shutil, subprocess, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from workloads.common import parse_args, level, deadline, workdir


def main():
    a = parse_args(__doc__)
    child_every = level(a.intensity, 2.0, 1.0, 0.5)      # seconds between short children
    d = workdir("mixed_normal")
    end, last_child, n = deadline(a.duration), 0.0, 0
    try:
        while time.monotonic() < end:
            s = sum(i * i for i in range(20000))
            p = os.path.join(d, "f%d.txt" % (n % 5))
            with open(p, "w") as f:
                f.write(str(s) * 50)
            with open(p) as f:
                f.read()
            if time.monotonic() - last_child > child_every:
                subprocess.run(["/bin/true"], check=False)
                last_child = time.monotonic()
            n += 1
            time.sleep(0.05)
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    main()
