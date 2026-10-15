"""Append-only JSONL audit log (FR-13). One line per decision/action; flushed immediately."""
from __future__ import annotations
import json
import time
from pathlib import Path


class AuditLog:
    def __init__(self, path, run_id="run"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.f = open(path, "a", buffering=1)
        self.run_id = run_id

    def write(self, **rec):
        rec.setdefault("ts_ns", time.monotonic_ns())
        rec.setdefault("wall", time.time())
        rec["run_id"] = self.run_id
        self.f.write(json.dumps(rec, default=str) + "\n")

    def close(self):
        self.f.close()
