"""Supervisor: launches test workloads, registers them in the allow-list, and (Level 5) restarts a controlled
application that was terminated by the remediation layer."""
from __future__ import annotations
import subprocess
import sys
import time
from pathlib import Path

from .safety import Registry

ROOT = Path(__file__).resolve().parents[1]


class Supervisor:
    def __init__(self, registry: Registry, max_restarts: int = 1):
        self.reg, self.max_restarts = registry, max_restarts
        self.procs: dict[int, subprocess.Popen] = {}
        self.cmds: dict[int, list] = {}

    def launch(self, name: str, cmd: list, kind="normal", restartable=False) -> int:
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t = self.reg.register(p.pid, name, kind, restart_cmd=cmd if restartable else None)
        self.procs[p.pid] = p
        self.cmds[p.pid] = cmd
        t.restarts = 0
        return p.pid

    def launch_workload(self, script: str, kind: str, duration: float, intensity: str = "medium",
                        restartable=False, extra: list | None = None) -> int:
        path = ROOT / "workloads" / ("normal" if kind == "normal" else "anomalous") / f"{script}.py"
        if not path.exists():
            raise FileNotFoundError(path)
        cmd = [sys.executable, str(path), "--duration", str(duration), "--intensity", intensity] + (extra or [])
        return self.launch(script, cmd, kind, restartable)

    def restart(self, old_pid: int) -> int | None:
        t = self.reg.targets.get(old_pid)
        if t is None or not t.restart_cmd or t.restarts >= self.max_restarts:
            return None
        self.reap(old_pid)
        new = self.launch(t.name, t.restart_cmd, "normal", True)
        self.reg.targets[new].restarts = t.restarts + 1
        self.reg.unregister(old_pid)
        return new

    def reap(self, pid: int):
        p = self.procs.get(pid)
        if p is not None:
            try:
                p.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass

    def alive(self, pid: int) -> bool:
        p = self.procs.get(pid)
        return p is not None and p.poll() is None

    def cleanup(self):
        for pid, p in self.procs.items():
            if p.poll() is None:
                try:
                    p.kill()
                    p.wait(timeout=2)
                except Exception:
                    pass
