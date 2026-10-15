#!/usr/bin/env python3
"""Generate feature_engine/config/syscalls_<arch>.json from the system's
unistd header so syscall numbers in the CSVs can be mapped to names.
Syscall numbers are architecture specific; run this on the machine you trace."""
import json, platform, re, sys, pathlib

ARCH = platform.machine()
CANDIDATES = {
    "x86_64": ["/usr/include/x86_64-linux-gnu/asm/unistd_64.h", "/usr/include/asm/unistd_64.h"],
    "aarch64": ["/usr/include/asm-generic/unistd.h", "/usr/include/aarch64-linux-gnu/asm/unistd.h"],
}
for p in CANDIDATES.get(ARCH, []):
    if pathlib.Path(p).exists():
        hdr = p
        break
else:
    sys.exit(f"no unistd header found for {ARCH}; install linux-libc-dev")

pat = re.compile(r"#define\s+__NR(?:3264)?_(\w+)\s+(\d+)\b")
table = {}
for line in open(hdr):
    m = pat.match(line)
    if m:
        table[int(m.group(2))] = m.group(1)
out = pathlib.Path(__file__).resolve().parents[1] / "feature_engine" / "config" / f"syscalls_{ARCH}.json"
out.write_text(json.dumps({str(k): v for k, v in sorted(table.items())}, indent=0))
print(f"{len(table)} syscalls from {hdr} -> {out}")
