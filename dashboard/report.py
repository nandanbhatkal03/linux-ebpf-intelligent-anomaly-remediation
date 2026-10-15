#!/usr/bin/env python3
"""Static HTML dashboard (FR-15, optional - nothing depends on it). Self-contained: charts are embedded PNGs.

  python -m dashboard.report --results results/phase2 --live results/phase2/live --out results/phase2/report.html"""
from __future__ import annotations
import argparse
import base64
import html
import io
import json
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def png(fig) -> str:
    b = io.BytesIO()
    fig.savefig(b, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return f'<img src="data:image/png;base64,{base64.b64encode(b.getvalue()).decode()}">'


def table(df: pd.DataFrame, fmt="{:.3f}") -> str:
    return df.to_html(index=False, border=0, classes="t", float_format=lambda x: fmt.format(x), na_rep="-")


def timeline(run_dir: Path, title: str) -> str:
    db = run_dir / "results.db"
    if not db.exists():
        return ""
    c = sqlite3.connect(db)
    d = pd.read_sql("select * from detections", c)
    a = pd.read_sql("select * from actions", c)
    if d.empty:
        return ""
    t0 = d.end_ns.min()
    fig, ax = plt.subplots(figsize=(9, 3.2))
    for (pid, comm), g in d.groupby(["pid", "comm"]):
        ax.plot((g.end_ns - t0) / 1e9, g.ratio, marker=".", label=f"{comm} [{pid}]")
    ax.axhline(1, color="orange", ls="--", lw=1, label="T1 (suspicious)")
    ax.set_yscale("log"); ax.set_xlabel("seconds"); ax.set_ylabel("score / T1"); ax.set_title(title)
    colors = {"alert": "gold", "restrict": "tab:orange", "suspend": "tab:red", "terminate": "black", "resume": "green", "unrestrict": "green"}
    for _, r in a.iterrows():
        if r.action in colors:
            ax.axvline((r.ts_ns - t0) / 1e9, color=colors[r.action], alpha=.7, lw=1.3)
            ax.text((r.ts_ns - t0) / 1e9, ax.get_ylim()[1], r.action, rotation=90, va="top", fontsize=7)
    ax.legend(fontsize=7, loc="upper left")
    return png(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default="results/phase2")
    ap.add_argument("--live", default="results/phase2/live")
    ap.add_argument("--out", default="results/phase2/report.html")
    a = ap.parse_args(argv)
    R, L = Path(a.results), Path(a.live)
    parts = ["<h1>eBPF anomaly detection &amp; remediation - results</h1>"]

    f = R / "model_comparison.csv"
    if f.exists():
        m = pd.read_csv(f)
        parts.append("<h2>Model comparison (held-out test runs)</h2>" + table(m[["model", "roc_auc", "f1", "precision", "recall", "fpr",
                     "event_recall", "median_latency_ms", "persistent_false_alarms", "infer_us_per_window"]]))
        fig, ax = plt.subplots(figsize=(6, 3))
        m.set_index("model")[["roc_auc", "f1", "event_recall"]].plot.bar(ax=ax, rot=0); ax.set_ylim(0, 1.05)
        parts.append(png(fig))
    for name, h in (("per_scenario.csv", "Per-scenario detection"), ("feature_ablation.csv", "Feature-group ablation (Isolation Forest)"),
                    ("window_size.csv", "Window-size study"), ("overhead_summary.csv", "Monitoring overhead"),
                    ("scalability.csv", "Scalability (concurrent processes)")):
        if (R / name).exists():
            parts.append(f"<h2>{h}</h2>" + table(pd.read_csv(R / name)))
    for arm in ("observe", "active"):
        if (L / arm).exists():
            parts.append(f"<h2>Live run: {arm}</h2>" + timeline(L / arm, f"{arm} arm"))
    for cmp in sorted(L.glob("*_comparison.csv")) if L.exists() else []:
        parts.append(f"<h2>Remediation impact: {cmp.stem}</h2>" + table(pd.read_csv(cmp).set_index("arm").T.reset_index()))
    for arm, col in (("observe", "tab:red"), ("active", "tab:blue")):
        pass
    vs = {arm: L / f"{arm}_victim.csv" for arm in ("observe", "active") if (L / f"{arm}_victim.csv").exists()}
    if vs:
        fig, ax = plt.subplots(figsize=(9, 3))
        for arm, p in vs.items():
            v = pd.read_csv(p)
            ax.plot((v.t_mono_ns - v.t_mono_ns.min()) / 1e9, v.samples, label=arm)
        ax.set_xlabel("seconds"); ax.set_ylabel("victim throughput (loops/s)"); ax.legend()
        parts.append("<h2>Application impact</h2>" + png(fig))
    css = "body{font-family:sans-serif;max-width:1000px;margin:2em auto}table.t{border-collapse:collapse;font-size:13px}.t td,.t th{padding:3px 9px;border-bottom:1px solid #ddd;text-align:right}"
    Path(a.out).write_text(f"<!doctype html><meta charset=utf-8><style>{css}</style>" + "\n".join(parts))
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
