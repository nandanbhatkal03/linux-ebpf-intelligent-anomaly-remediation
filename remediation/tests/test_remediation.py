import os, signal, subprocess, sys, time
from types import SimpleNamespace

import pytest

from remediation import actions, safety
from remediation.audit import AuditLog
from remediation.policy_engine import Policy, PolicyEngine
from remediation.remediation_engine import RemediationEngine
from remediation.supervisor import Supervisor


def det(pid, level, ratio=2.0, end_ns=1):
    return SimpleNamespace(pid=pid, level=level, ratio=ratio, score=ratio, end_ns=end_ns, comm="w")


def feed(e, pid, levels, t0=0, step=1_000_000_000):
    out = []
    for i, lv in enumerate(levels):
        out += e.on_detection(det(pid, lv, end_ns=i + 1), t0 + i * step)
    return out


# ---------------- policy engine (pure logic) ----------------
def test_normal_never_acts():
    e = PolicyEngine(Policy())
    assert feed(e, 5, ["normal"] * 50) == []


def test_single_spike_is_ignored_persistence():
    e = PolicyEngine(Policy())
    assert feed(e, 5, ["normal", "critical", "normal", "normal"]) == []


def test_alert_before_any_action_then_ladder():
    e = PolicyEngine(Policy(step_windows=2))
    acts = [d.action for d in feed(e, 5, ["suspicious", "suspicious"])]
    assert acts == ["alert"]                                     # first non-destructive step
    acts = [d.action for d in feed(PolicyEngine(Policy(step_windows=2)), 5, ["critical"] * 10)]
    assert acts[0] == "alert" and "restrict" in acts and acts.index("restrict") < acts.index("suspend") < acts.index("terminate")


def test_max_level_caps_ladder():
    e = PolicyEngine(Policy(max_level="restrict"))
    acts = [d.action for d in feed(e, 5, ["critical"] * 20)]
    assert "restrict" in acts and "suspend" not in acts and "terminate" not in acts


def test_recovery_lifts_restriction():
    e = PolicyEngine(Policy(recover_windows=3))
    feed(e, 5, ["critical"] * 3)
    acts = [d.action for d in feed(e, 5, ["normal"] * 4, t0=10 * 10**9)]
    assert "unrestrict" in acts


def test_suspend_hold_elapses_to_terminate_or_resume():
    e = PolicyEngine(Policy(step_windows=1, suspend_hold_s=2, max_level="terminate"))
    feed(e, 5, ["critical"] * 4)
    assert e.st(5).suspended_at_ns
    assert [d.action for d in e.on_tick(e.st(5).suspended_at_ns + 3 * 10**9)] == ["terminate"]
    e2 = PolicyEngine(Policy(step_windows=1, suspend_hold_s=2, max_level="suspend"))
    feed(e2, 5, ["critical"] * 4)
    assert [d.action for d in e2.on_tick(e2.st(5).suspended_at_ns + 3 * 10**9)] == ["resume"]


# ---------------- safety gate + real actions ----------------
@pytest.fixture
def sleeper():
    p = subprocess.Popen(["sleep", "60"])
    yield p
    p.kill(); p.wait()


def test_safety_blocks_unregistered_pid1_self(sleeper):
    reg = safety.Registry()
    assert safety.check(reg, sleeper.pid)[0] is False          # not in allow-list
    assert safety.check(reg, 1)[0] is False
    assert safety.check(reg, os.getpid())[0] is False
    with pytest.raises(ValueError):
        reg.register(1, "init")


def test_safety_allows_registered_and_descendants_and_detects_pid_reuse(sleeper):
    reg = safety.Registry()
    reg.register(sleeper.pid, "sleep")
    assert safety.check(reg, sleeper.pid)[0] is True
    reg.targets[sleeper.pid].start_time += 1                   # simulate a recycled PID
    assert safety.check(reg, sleeper.pid)[0] is False


def test_actions_restrict_suspend_resume_terminate(sleeper):
    pid = sleeper.pid
    ok, _ = actions.restrict(pid); assert ok and os.getpriority(os.PRIO_PROCESS, pid) == 19
    actions.unrestrict(pid); assert os.getpriority(os.PRIO_PROCESS, pid) == 0
    ok, _ = actions.suspend(pid); assert ok
    time.sleep(0.2)
    assert open(f"/proc/{pid}/stat").read().split(")")[-1].split()[0] == "T"
    actions.resume(pid); time.sleep(0.2)
    assert open(f"/proc/{pid}/stat").read().split(")")[-1].split()[0] in "SR"
    ok, _ = actions.terminate(pid); assert ok
    sleeper.wait(timeout=3)
    assert sleeper.returncode in (-signal.SIGTERM, -signal.SIGKILL)


def test_engine_blocks_non_allowlisted_and_dry_run_does_nothing(tmp_path, sleeper):
    reg = safety.Registry()
    audit = AuditLog(tmp_path / "a.jsonl")
    eng = RemediationEngine(reg, audit)
    from remediation.policy_engine import Decision
    r = eng.execute(Decision(sleeper.pid, "terminate", "test"))
    assert not r["ok"] and "BLOCKED" in r["detail"] and sleeper.poll() is None       # untouched
    reg.register(sleeper.pid, "sleep")
    dry = RemediationEngine(reg, audit, dry_run=True)
    r = dry.execute(Decision(sleeper.pid, "terminate", "test"))
    assert r["ok"] and r["detail"].startswith("dry-run") and sleeper.poll() is None
    live = RemediationEngine(reg, audit)
    r = live.execute(Decision(sleeper.pid, "terminate", "test"))
    assert r["ok"] and sleeper.wait(timeout=3) is not None
    assert (tmp_path / "a.jsonl").read_text().count("\n") == 3                       # every attempt audited


def test_supervisor_restart(tmp_path):
    reg = safety.Registry(); sup = Supervisor(reg, max_restarts=1)
    pid = sup.launch("sleeper", ["sleep", "60"], restartable=True)
    actions.terminate(pid); sup.procs[pid].wait(timeout=3)
    new = sup.restart(pid)
    assert new and new != pid and sup.alive(new)
    actions.terminate(new); sup.procs[new].wait(timeout=3)
    assert sup.restart(new) is None                                                   # restart budget exhausted
    sup.cleanup()
