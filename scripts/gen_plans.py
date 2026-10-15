#!/usr/bin/env python3
"""Generate the workload plans for the Phase-II dataset (deterministic).
train_*: normal only, varied intensity.  test_*: normal background + 5 anomaly scenarios in sequence."""
import itertools, pathlib, yaml

OUT = pathlib.Path(__file__).resolve().parents[1] / "workloads" / "configs" / "generated"
OUT.mkdir(parents=True, exist_ok=True)
I = ["low", "medium", "high"]

def e(name, kind, dur, inten, start): return dict(name=name, kind=kind, duration=dur, intensity=inten, start_after=start)

def train(k):
    a, b = I[k % 3], I[(k + 1) % 3]
    s = [e("cpu_workload", "normal", 38, a, 0), e("io_workload", "normal", 38, b, 0),
         e("mixed_workload", "normal", 38, I[(k + 2) % 3], 0),
         e("cpu_workload", "normal", 38, b, 40), e("memory_workload", "normal", 38, "low" if k % 2 else "medium", 40),
         e("mixed_workload", "normal", 38, a, 40)]
    return dict(schedule=s)

SC = ["cpu_pressure", "memory_pressure", "process_burst", "syscall_burst", "io_burst"]
def test(k):
    inten = I[k % 3]
    bg = [e("cpu_workload", "normal", 96, "medium", 0), e("mixed_workload", "normal", 96, "medium", 0),
          e("io_workload", "normal", 96, "low", 0)]
    order = SC[k % 5:] + SC[:k % 5]
    an = [e(n, "anomalous", 10, inten, 8 + 17 * i) for i, n in enumerate(order)]
    return dict(schedule=bg + an)

for k in range(5):
    (OUT / f"train_{k}.yaml").write_text(yaml.safe_dump(train(k), sort_keys=False))
for k in range(6):
    (OUT / f"test_{k}.yaml").write_text(yaml.safe_dump(test(k), sort_keys=False))
print("plans:", sorted(p.name for p in OUT.iterdir()))
