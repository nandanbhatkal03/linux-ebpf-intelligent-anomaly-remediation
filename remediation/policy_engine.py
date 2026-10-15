"""Policy engine: Detection -> Decision (package sections 13 / 15.6). Pure logic, no side effects (unit-testable).

State machine per PID:
  NORMAL --(>= suspicious_windows consecutive score>=T1)--> SUSPICIOUS   -> ALERT (once, then every re-alert_s)
  SUSPICIOUS/any --(>= critical_windows consecutive score>=T2, or >= escalate_suspicious windows >=T1)--> CRITICAL
  CRITICAL walks the ladder: restrict -> suspend -> terminate, one rung per `step_windows` windows (or `step_s` of
  silence for a suspended process) while the anomaly persists. A pid that stays normal for `recover_windows` is
  un-restricted / resumed. Non-destructive actions come first; `max_level` caps the ladder."""
from __future__ import annotations
from dataclasses import dataclass, field

LADDER = ["alert", "restrict", "suspend", "terminate"]


@dataclass
class Policy:
    suspicious_windows: int = 2
    critical_windows: int = 2
    escalate_suspicious: int = 6
    step_windows: int = 2
    recover_windows: int = 5
    suspend_hold_s: float = 3.0
    realert_s: float = 10.0
    max_level: str = "terminate"          # alert | restrict | suspend | terminate
    dry_run: bool = False
    restart_on_terminate: bool = False
    warmup_s: float = 3.0              # ignore detections during a target's first seconds (start-up transients)

    @staticmethod
    def from_dict(d: dict) -> "Policy":
        known = Policy.__dataclass_fields__
        return Policy(**{k: v for k, v in (d or {}).items() if k in known})


@dataclass
class Decision:
    pid: int
    action: str                    # alert | restrict | suspend | resume | unrestrict | terminate | restart
    reason: str
    score: float = 0.0
    ratio: float = 0.0
    state: str = "normal"


@dataclass
class PidState:
    sus_run: int = 0
    crit_run: int = 0
    sus_total_run: int = 0
    normal_run: int = 0
    level: int = 0                 # index into LADDER reached (0 = none)
    windows_at_level: int = 0
    last_alert_ns: int = 0
    suspended_at_ns: int = 0
    state: str = "normal"
    applied: list = field(default_factory=list)


class PolicyEngine:
    def __init__(self, policy: Policy | None = None):
        self.p = policy or Policy()
        self.state: dict[int, PidState] = {}
        self.max_idx = LADDER.index(self.p.max_level)

    def st(self, pid: int) -> PidState:
        return self.state.setdefault(pid, PidState())

    def on_detection(self, d, now_ns: int) -> list[Decision]:
        """d: runtime.live_detector.Detection (only .pid .level .score .ratio used)."""
        s, p, out = self.st(d.pid), self.p, []
        sus, crit = d.level in ("suspicious", "critical"), d.level == "critical"
        s.sus_run = s.sus_run + 1 if sus else 0
        s.sus_total_run = s.sus_total_run + 1 if sus else 0
        s.crit_run = s.crit_run + 1 if crit else 0
        s.normal_run = 0 if sus else s.normal_run + 1
        mk = lambda a, r: Decision(d.pid, a, r, d.score, d.ratio, s.state)

        if not sus:
            if s.normal_run >= p.recover_windows and s.level > 0:
                for a in reversed(s.applied):
                    if a == "restrict":
                        out.append(mk("unrestrict", f"normal for {s.normal_run} windows"))
                    elif a == "suspend":
                        out.append(mk("resume", f"normal for {s.normal_run} windows"))
                s.level, s.applied, s.state, s.windows_at_level = 0, [], "normal", 0
            elif s.normal_run >= p.recover_windows:
                s.state = "normal"
            return out

        if s.state == "normal" and s.sus_run >= p.suspicious_windows:
            s.state = "suspicious"
        if s.state == "suspicious" and (s.crit_run >= p.critical_windows or s.sus_total_run >= p.escalate_suspicious):
            s.state = "critical"

        if s.state in ("suspicious", "critical") and s.level == 0 and d.end_ns and \
                (now_ns - s.last_alert_ns > p.realert_s * 1e9 or s.last_alert_ns == 0):
            s.last_alert_ns = now_ns
            out.append(mk("alert", f"{s.state}: {s.sus_run} windows >= T1, ratio {d.ratio:.2f}"))

        if s.state == "critical":
            s.windows_at_level += 1
            target = 1 if s.level == 0 else s.level + (1 if s.windows_at_level > p.step_windows else 0)
            target = min(target, self.max_idx, len(LADDER) - 1)
            if target >= 1 and target > s.level and LADDER[target] != "alert":
                s.level, s.windows_at_level = target, 0
                a = LADDER[target]
                s.applied.append(a)
                out.append(mk(a, f"critical: ratio {d.ratio:.2f}, escalating to {a}"))
                if a == "suspend":
                    s.suspended_at_ns = now_ns
        return out

    def on_tick(self, now_ns: int) -> list[Decision]:
        """Time-driven rules: a suspended process produces no windows, so its hold timer must run on the clock."""
        out = []
        for pid, s in self.state.items():
            if "suspend" in s.applied and "terminate" not in s.applied and s.suspended_at_ns and \
                    (now_ns - s.suspended_at_ns) / 1e9 >= self.p.suspend_hold_s:
                if self.max_idx >= LADDER.index("terminate"):
                    s.applied.append("terminate")
                    s.level = LADDER.index("terminate")
                    s.suspended_at_ns = 0
                    out.append(Decision(pid, "terminate", f"still anomalous after {self.p.suspend_hold_s}s suspension", state="critical"))
                else:
                    s.applied.remove("suspend")
                    s.suspended_at_ns = 0
                    s.state, s.sus_run, s.crit_run, s.sus_total_run = "suspicious", 0, 0, 0
                    out.append(Decision(pid, "resume", "suspension hold elapsed (max_level below terminate)", state="suspicious"))
        return out

    def forget(self, pid: int):
        self.state.pop(pid, None)
