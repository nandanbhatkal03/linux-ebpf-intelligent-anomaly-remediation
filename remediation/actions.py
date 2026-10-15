"""Remediation primitives (package section 13, levels 2-5). Each returns (ok, detail) and is reversible where possible.

  restrict    renice to 19 for every thread of the process tree (+ cgroup-v2 cpu.max when writable)
  unrestrict  restore the original nice values
  suspend     SIGSTOP the tree        resume   SIGCONT
  terminate   SIGTERM, grace period, then SIGKILL (tree)
All functions assume `safety.check()` has already passed; they additionally tolerate processes vanishing."""
from __future__ import annotations
import os
import signal
import time

from .safety import descendants

_orig_nice: dict[int, int] = {}


def _tids(pid: int) -> list[int]:
    try:
        return [int(t) for t in os.listdir(f"/proc/{pid}/task")]
    except OSError:
        return []


def _tree(pid: int) -> list[int]:
    return [pid] + descendants(pid)


def restrict(pid: int, nice: int = 19) -> tuple[bool, str]:
    n = 0
    for p in _tree(pid):
        for t in _tids(p):
            try:
                if t not in _orig_nice:
                    _orig_nice[t] = os.getpriority(os.PRIO_PROCESS, t)
                os.setpriority(os.PRIO_PROCESS, t, nice)
                n += 1
            except OSError:
                pass
    return n > 0, f"nice={nice} on {n} threads"


def unrestrict(pid: int) -> tuple[bool, str]:
    n = 0
    for t, old in list(_orig_nice.items()):
        try:
            os.setpriority(os.PRIO_PROCESS, t, old)
            n += 1
        except OSError:
            pass
        _orig_nice.pop(t, None)
    return True, f"restored {n} threads"


def _signal_tree(pid: int, sig) -> int:
    n = 0
    for p in reversed(_tree(pid)):          # leaves first
        try:
            os.kill(p, sig)
            n += 1
        except ProcessLookupError:
            pass
        except PermissionError:
            pass
    return n


def suspend(pid: int) -> tuple[bool, str]:
    n = _signal_tree(pid, signal.SIGSTOP)
    return n > 0, f"SIGSTOP x{n}"


def resume(pid: int) -> tuple[bool, str]:
    n = _signal_tree(pid, signal.SIGCONT)
    return n > 0, f"SIGCONT x{n}"


def terminate(pid: int, grace_s: float = 2.0) -> tuple[bool, str]:
    tree = _tree(pid)
    _signal_tree(pid, signal.SIGCONT)       # a stopped process cannot handle SIGTERM
    _signal_tree(pid, signal.SIGTERM)
    t = time.time()
    while time.time() - t < grace_s:
        if not any(os.path.exists(f"/proc/{p}") and _alive(p) for p in tree):
            return True, "SIGTERM"
        time.sleep(0.05)
    _signal_tree(pid, signal.SIGKILL)
    time.sleep(0.1)
    return not any(_alive(p) for p in tree), "SIGKILL after grace"


def _alive(pid: int) -> bool:
    try:
        st = open(f"/proc/{pid}/stat").read()
        return st[st.rindex(")") + 2] != "Z"      # zombies are dead for our purposes
    except OSError:
        return False
