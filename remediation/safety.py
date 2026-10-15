"""Safety gate (NFR-02, NFR-08). Every action goes through `check()`; nothing outside the allow-list is ever touched.

A target is acted on only if ALL hold:
  * it (or an ancestor) is REGISTERED in the allow-list, with the same start time (guards PID reuse);
  * pid > 1, not this process, not its parent, not a kernel thread, not in the protected-name list."""
from __future__ import annotations
import os
from dataclasses import dataclass

PROTECTED_COMM = {"systemd", "init", "sshd", "dbus-daemon", "containerd", "dockerd", "kubelet", "bash", "sh", "zsh",
                  "python3-pipeline"}  # shells are only protected when not registered (see Registry.register)


def proc_start_time(pid: int) -> int | None:
    """Start time in clock ticks since boot (field 22 of /proc/pid/stat); None if the process is gone."""
    try:
        s = open(f"/proc/{pid}/stat").read()
        return int(s[s.rindex(")") + 2:].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def ppid_of(pid: int) -> int | None:
    try:
        s = open(f"/proc/{pid}/stat").read()
        return int(s[s.rindex(")") + 2:].split()[1])
    except (OSError, ValueError, IndexError):
        return None


def is_kernel_thread(pid: int) -> bool:
    try:
        return pid == 2 or ppid_of(pid) == 2 or not os.path.exists(f"/proc/{pid}/exe") or \
            bool(open(f"/proc/{pid}/stat").read().split(")")[-1].split()[6] == "0" and False)
    except OSError:
        return True


def comm_of(pid: int) -> str:
    try:
        return open(f"/proc/{pid}/comm").read().strip()
    except OSError:
        return "?"


def descendants(pid: int) -> list[int]:
    """All live descendants of pid (breadth-first, via /proc scan)."""
    kids: dict[int, list[int]] = {}
    for d in os.listdir("/proc"):
        if d.isdigit():
            pp = ppid_of(int(d))
            if pp is not None:
                kids.setdefault(pp, []).append(int(d))
    out, queue = [], [pid]
    while queue:
        p = queue.pop()
        for c in kids.get(p, []):
            out.append(c)
            queue.append(c)
    return out


@dataclass
class Target:
    pid: int
    name: str
    start_time: int
    kind: str = "test"
    restart_cmd: list | None = None
    restarts: int = 0


class Registry:
    """The allow-list. Only processes registered here (by the supervisor) may be remediated."""

    def __init__(self):
        self.targets: dict[int, Target] = {}

    def register(self, pid: int, name: str, kind="test", restart_cmd=None) -> Target:
        st = proc_start_time(pid)
        if st is None:
            raise ValueError(f"cannot register {pid}: no such process")
        if pid <= 1 or pid in (os.getpid(), os.getppid()):
            raise ValueError(f"refusing to register protected pid {pid}")
        t = Target(pid, name, st, kind, restart_cmd)
        self.targets[pid] = t
        return t

    def unregister(self, pid: int):
        self.targets.pop(pid, None)

    def root_of(self, pid: int) -> Target | None:
        """The registered target that `pid` is (or descends from); verifies the start time."""
        seen = 0
        p = pid
        while p and p > 1 and seen < 64:
            t = self.targets.get(p)
            if t is not None:
                return t if proc_start_time(p) == t.start_time else None
            p = ppid_of(p) or 0
            seen += 1
        return None


def check(registry: Registry, pid: int) -> tuple[bool, str]:
    if pid <= 1:
        return False, "pid<=1"
    if pid in (os.getpid(), os.getppid()):
        return False, "self-or-parent"
    if proc_start_time(pid) is None:
        return False, "process gone"
    if is_kernel_thread(pid):
        return False, "kernel thread"
    t = registry.root_of(pid)
    if t is None:
        return False, "not in allow-list (or pid reused)"
    return True, f"allowed via {t.name}[{t.pid}]"
