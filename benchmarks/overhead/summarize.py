#!/usr/bin/env python3
"""Summarise run_overhead.sh output: mean, std, and % overhead vs the baseline config."""
import sys
from pathlib import Path

import pandas as pd

raw = Path(sys.argv[1])
d = pd.read_csv(raw)
g = d.groupby(["metric", "config"])["value"].agg(["mean", "std", "count"]).reset_index()
base = g[g.config == "baseline"].set_index("metric")["mean"]
g["overhead_pct"] = g.apply(lambda r: 100.0 * (r["mean"] - base[r["metric"]]) / base[r["metric"]], axis=1)
out = raw.parents[1] / "processed" / (raw.stem + "_summary.csv")
out.parent.mkdir(parents=True, exist_ok=True)
g.round(3).to_csv(out, index=False)
print(g.round(2).to_string(index=False))
print(f"\nsummary: {out}")
