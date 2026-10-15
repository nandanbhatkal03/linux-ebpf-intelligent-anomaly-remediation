#!/usr/bin/env bash
# Verifies that this machine can build and run the eBPF framework (NFR-10).
ok=1; pass(){ printf "  [ ok ] %s\n" "$*"; }; fail(){ printf "  [FAIL] %s\n" "$*"; ok=0; }; warn(){ printf "  [warn] %s\n" "$*"; }
echo "== Kernel =="
KV=$(uname -r); MAJ=${KV%%.*}; MIN=${KV#*.}; MIN=${MIN%%.*}
if (( MAJ > 5 || (MAJ == 5 && MIN >= 8) )); then pass "kernel $KV (>= 5.8: BPF ring buffer)"; else fail "kernel $KV < 5.8 (no BPF_MAP_TYPE_RINGBUF)"; fi
[[ -r /sys/kernel/btf/vmlinux ]] && pass "BTF available (/sys/kernel/btf/vmlinux): CO-RE works" || fail "no BTF: need CONFIG_DEBUG_INFO_BTF=y"
[[ "$(uname -m)" =~ ^(x86_64|aarch64)$ ]] && pass "arch $(uname -m)" || warn "arch $(uname -m) untested"
if [[ -d /sys/kernel/tracing/events || -d /sys/kernel/debug/tracing/events ]]; then pass "tracefs mounted"; else warn "tracefs not mounted (sudo mount -t tracefs nodev /sys/kernel/tracing)"; fi
for tp in raw_syscalls/sys_enter sched/sched_switch sched/sched_process_fork sched/sched_process_exec sched/sched_process_exit; do
  [[ -d /sys/kernel/tracing/events/$tp || -d /sys/kernel/debug/tracing/events/$tp ]] && pass "tracepoint $tp" || warn "tracepoint $tp not visible (needs root/tracefs)"; done
[[ -d /sys/kernel/tracing/events/exceptions/page_fault_user ]] && pass "tracepoint exceptions/page_fault_user (page-fault feature on)" || warn "no page_fault_user tracepoint: page_faults will be 0"
echo "== Privileges =="
if [[ $EUID -eq 0 ]]; then pass "running as root"; else warn "not root: use sudo to load BPF programs (or grant CAP_BPF,CAP_PERFMON)"; fi
echo "== Toolchain =="
command -v clang >/dev/null && pass "clang $(clang --version | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)" || fail "clang missing"
command -v gcc >/dev/null && pass "gcc" || fail "gcc missing"
command -v make >/dev/null && pass "make" || fail "make missing"
pkg-config --exists libbpf 2>/dev/null && pass "libbpf $(pkg-config --modversion libbpf)" || fail "libbpf-dev missing"
BT=""; for b in /usr/lib/linux-tools/*/bpftool $(command -v bpftool 2>/dev/null); do "$b" version >/dev/null 2>&1 && { BT=$b; break; }; done
[[ -n "$BT" ]] && pass "bpftool: $BT" || fail "no working bpftool (sudo apt install linux-tools-generic; the /usr/sbin wrapper fails if it does not match your kernel)"
echo "== Python =="
python3 - <<'PY' || ok=0
import importlib, sys
for m in ("pandas", "numpy", "yaml", "sklearn", "pytest"):
    try:
        importlib.import_module(m); print(f"  [ ok ] python: {m}")
    except Exception:
        print(f"  [FAIL] python module {m} missing (pip install -r requirements/python.txt)")
        sys.exit(1)
PY
echo; (( ok )) && echo "Environment OK." || { echo "Environment NOT ready - see FAIL lines."; exit 1; }
