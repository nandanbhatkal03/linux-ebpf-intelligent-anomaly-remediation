"""Synthetic collector run directories so the feature engine is testable without root/eBPF."""
import json
import pandas as pd
import pytest

S = 1_000_000_000          # 1 s in ns
T0 = 1_000 * S


@pytest.fixture
def make_run(tmp_path):
    def _make(sys_rows, res_rows=(), proc_rows=(), n_windows=6, window_ms=1000, run_id="t"):
        d = tmp_path / run_id
        d.mkdir()
        end = T0 + n_windows * window_ms * 1_000_000 + 400_000_000    # + a partial tail window
        (d / "meta.json").write_text(json.dumps({
            "run_id": run_id, "kernel": "x", "arch": "x86_64", "ncpu": 1, "window_ms": window_ms,
            "start_monotonic_ns": T0, "end_monotonic_ns": end}))
        pd.DataFrame(sys_rows, columns=["window_start_ns", "window_end_ns", "pid", "comm", "nr", "count"]
                     ).to_csv(d / "syscall_windows.csv", index=False)
        pd.DataFrame(res_rows, columns=["window_start_ns", "window_end_ns", "pid", "comm", "cpu_ns",
                                        "switches", "invol_switches", "page_faults"]
                     ).to_csv(d / "resource_windows.csv", index=False)
        pd.DataFrame(proc_rows, columns=["ts_ns", "event", "pid", "ppid", "uid", "gid", "value", "comm"]
                     ).to_csv(d / "process_events.csv", index=False)
        return d
    return _make


def win(k, ms=1000):
    return T0 + k * ms * 1_000_000, T0 + (k + 1) * ms * 1_000_000
