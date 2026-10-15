"""Executes policy Decisions through the safety gate, audits every attempt, and measures remediation latency
(anomaly decision -> action completion)."""
from __future__ import annotations
import time

from . import actions, safety
from .audit import AuditLog
from .policy_engine import Decision

ACT = {"restrict": actions.restrict, "unrestrict": actions.unrestrict, "suspend": actions.suspend,
       "resume": actions.resume, "terminate": actions.terminate}


class RemediationEngine:
    def __init__(self, registry: safety.Registry, audit: AuditLog, dry_run: bool = False, store=None, run_id="run",
                 supervisor=None, restart_on_terminate: bool = False):
        self.reg, self.audit, self.dry, self.store, self.run_id = registry, audit, dry_run, store, run_id
        self.sup, self.restart = supervisor, restart_on_terminate
        self.history: list[dict] = []

    def execute(self, dec: Decision, comm: str = "?", decided_ns: int | None = None) -> dict:
        t_start = time.monotonic_ns()
        rec = dict(pid=dec.pid, comm=comm, action=dec.action, reason=dec.reason, score=dec.score, ratio=dec.ratio,
                   dry_run=self.dry, ts_ns=t_start, ok=False, detail="")
        if dec.action == "alert":                                  # alerts never touch the process
            rec.update(ok=True, detail="alert logged")
        else:
            allowed, why = safety.check(self.reg, dec.pid)
            if dec.action in ("resume", "unrestrict") and not allowed and why == "process gone":
                allowed, why = True, "process gone (nothing to undo)"
            rec["safety"] = why
            if not allowed:
                rec.update(ok=False, detail=f"BLOCKED by safety gate: {why}", action=dec.action)
            elif self.dry:
                rec.update(ok=True, detail="dry-run: not executed")
            else:
                root = self.reg.root_of(dec.pid)
                target = root.pid if root else dec.pid            # act on the allow-listed root and its tree
                ok, detail = ACT[dec.action](target)
                rec.update(ok=ok, detail=detail, target_pid=target)
                if dec.action == "terminate" and ok and self.restart and self.sup is not None:
                    new = self.sup.restart(target)
                    if new:
                        self.audit.write(pid=target, comm=comm, action="restart", ok=True, detail=f"restarted as pid {new}")
        t_end = time.monotonic_ns()
        rec["latency_ms"] = (t_end - (decided_ns or t_start)) / 1e6
        rec["done_ns"] = t_end
        self.audit.write(**rec)
        if self.store:
            self.store.action(self.run_id, rec)
        self.history.append(rec)
        return rec
