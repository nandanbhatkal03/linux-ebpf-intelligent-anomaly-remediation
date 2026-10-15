import math

import numpy as np
import pandas as pd

from feature_engine.src.event_parser import load_run
from feature_engine.src.labeling import apply_labels
from feature_engine.src.syscall_features import build_category_map, shannon_entropy, syscall_names
from feature_engine.src.windowing import build_features, feature_columns, load_config
from feature_engine.src.feature_selection import select_features
from .conftest import S, T0, win


def test_entropy_uniform_and_degenerate():
    assert shannon_entropy(np.array([5, 5, 5, 5])) == 2.0          # log2(4)
    assert shannon_entropy(np.array([10, 0, 0])) == 0.0
    assert shannon_entropy(np.array([])) == 0.0


def test_syscall_table_and_categories():
    names = syscall_names("x86_64")
    assert names[0] == "read" and names[59] == "execve" and names[9] == "mmap"
    cfg = load_config()
    cm = build_category_map(cfg["syscall_categories"], "other", names)
    assert cm[0] == "file" and cm[9] == "memory" and cm[41] == "network"      # read, mmap, socket
    assert cm[59] == "process" and cm[202] == "ipc"                            # execve, futex


def test_window_features_basic(make_run):
    s0, e0 = win(0)
    sys_rows = [(s0, e0, 10, "app", 0, 30), (s0, e0, 10, "app", 1, 10),        # read x30, write x10
                (s0, e0, 10, "app", 9, 60)]                                    # mmap x60
    res_rows = [(s0, e0, 10, "app", 250_000_000, 4, 1, 7)]
    f = build_features(load_run(make_run(sys_rows, res_rows)), load_config())
    r = f.iloc[0]
    assert r["pid"] == 10 and r["widx"] == 0 and r["comm"] == "app"
    assert r["sys_total"] == 100 and r["sys_unique"] == 3
    assert math.isclose(r["sys_entropy"], shannon_entropy(np.array([30, 10, 60])))
    assert r["cat_file"] == 40 and r["cat_memory"] == 60
    assert math.isclose(r["frac_memory"], 0.6)
    assert math.isclose(r["cpu_util"], 0.25) and r["invol_ratio"] == 0.25 and r["page_faults"] == 7


def test_tail_window_dropped_and_idle_rows_filtered(make_run):
    rows = [(*win(5), 1, "a", 0, 5),          # window 5 is the last COMPLETE one (n_windows=6)
            (T0 + 6 * S, T0 + 6 * S + 400_000_000, 1, "a", 0, 99)]    # partial tail -> dropped
    f = build_features(load_run(make_run(rows)), load_config())
    assert list(f["widx"]) == [5]


def test_rewindow_merges_collector_windows(make_run):
    rows = [(*win(0, 500), 1, "a", 0, 10), (*win(1, 500), 1, "a", 0, 15)]
    cfg = load_config(); cfg["window_ms"] = 1000
    f = build_features(load_run(make_run(rows, window_ms=500)), cfg)
    assert len(f) == 1 and f.iloc[0]["sys_total"] == 25


def test_temporal_history_excludes_current_window(make_run):
    rows = [(*win(k), 1, "a", 0, c) for k, c in enumerate([10, 10, 10, 10, 1000])]
    f = build_features(load_run(make_run(rows)), load_config()).sort_values("widx")
    last = f.iloc[-1]
    assert last["sys_total"] == 1000
    assert last["sys_total_rmean"] == 10                # spike NOT included in its own baseline
    assert last["sys_total_delta"] == 990


def test_process_counts_and_labels_follow_lineage(make_run):
    rows = [(*win(k), pid, "w", 0, 50) for k in (1, 2) for pid in (100, 101, 7)]
    proc = [(T0 + 1_100_000_000, "fork", 100, 1, 0, 0, 101, "w"),     # 101 is child of 100
            (T0 + 1_200_000_000, "exec", 101, 100, 0, 0, 101, "true")]
    d = make_run(rows, proc_rows=proc)
    run = load_run(d)
    f = build_features(run, load_config())
    assert f[(f.pid == 100) & (f.widx == 1)]["n_fork"].iloc[0] == 1
    assert f[(f.pid == 101) & (f.widx == 1)]["n_exec"].iloc[0] == 1
    labels = pd.DataFrame([["t", "process_burst", "anomalous", 100, T0 + 2 * S, T0 + 3 * S]],
                          columns=["run_id", "workload", "kind", "pid", "start_ns", "end_ns"])
    g = apply_labels(f, run.proc, labels, scope="tree").set_index(["pid", "widx"])
    assert g.loc[(100, 2), "label"] == 1 and g.loc[(101, 2), "label"] == 1   # child inherits label
    r = apply_labels(f, run.proc, labels).set_index(["pid", "widx"])         # default scope=root
    assert r.loc[(100, 2), "label"] == 1 and r.loc[(101, 2), "label"] == -1
    assert g.loc[(100, 1), "label"] == -1                                      # before the interval
    assert g.loc[(7, 2), "label"] == -1                                        # unrelated background


def test_feature_selection_drops_constant_and_duplicates():
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 4, 6, 8], "c": [5, 5, 5, 5], "d": [4, 1, 3, 2]})
    keep, dropped = select_features(df, ["a", "b", "c", "d"])
    assert "c" in dropped and dropped["c"] == "constant"
    assert not ({"a", "b"} <= set(keep))               # perfectly correlated pair collapses to one
    assert "d" in keep
