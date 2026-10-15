"""SQLite result store (FR-13/FR-14): runs, detections, actions, metrics. Stdlib only."""
from __future__ import annotations
import json
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, started REAL, model TEXT, policy TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS detections(run_id TEXT, widx INT, end_ns INT, decided_ns INT, pid INT, comm TEXT,
  score REAL, ratio REAL, level TEXT, top_features TEXT);
CREATE TABLE IF NOT EXISTS actions(run_id TEXT, ts_ns INT, pid INT, comm TEXT, action TEXT, ok INT, dry_run INT,
  detail TEXT, score REAL, ratio REAL, latency_ms REAL);
CREATE TABLE IF NOT EXISTS metrics(run_id TEXT, ts_ns INT, name TEXT, value REAL);
CREATE INDEX IF NOT EXISTS d_run ON detections(run_id, pid);
"""


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA)

    def start_run(self, run_id, model="", policy="", notes=""):
        self.db.execute("INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?)", (run_id, time.time(), model, policy, notes))
        self.db.commit()

    def detections(self, run_id, dets):
        self.db.executemany("INSERT INTO detections VALUES(?,?,?,?,?,?,?,?,?,?)",
                            [(run_id, d.widx, d.end_ns, d.decided_ns, d.pid, d.comm, d.score, d.ratio, d.level,
                              json.dumps(d.top_features)) for d in dets])
        self.db.commit()

    def action(self, run_id, rec: dict):
        self.db.execute("INSERT INTO actions VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (run_id, rec.get("ts_ns"), rec.get("pid"), rec.get("comm"), rec.get("action"), int(rec.get("ok", 0)),
                         int(rec.get("dry_run", 0)), rec.get("detail", ""), rec.get("score"), rec.get("ratio"), rec.get("latency_ms")))
        self.db.commit()

    def metric(self, run_id, ts_ns, name, value):
        self.db.execute("INSERT INTO metrics VALUES(?,?,?,?)", (run_id, ts_ns, name, float(value)))

    def q(self, sql, args=()):
        return self.db.execute(sql, args).fetchall()

    def close(self):
        self.db.commit()
        self.db.close()
