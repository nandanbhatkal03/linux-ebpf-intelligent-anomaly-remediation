import numpy as np
import pandas as pd
import pytest

from ml.bundle import Bundle, train_bundle
from ml.evaluation.detection_eval import evaluate_bundle
from ml.models import REGISTRY


def synth(n=300, seed=0):
    r = np.random.default_rng(seed)
    X = pd.DataFrame({"a": r.normal(100, 10, n), "b": r.normal(0.3, 0.05, n), "c": r.poisson(3, n).astype(float), "d": r.normal(5, 1, n)})
    return X


def mkdf(X, label, run, scen=""):
    d = X.copy()
    d["run_id"], d["label"], d["scenario"], d["pid"] = run, label, scen, 10
    d["widx"] = range(len(d)); d["start_ns"] = d.widx * 10**9; d["end_ns"] = d.start_ns + 10**9; d["wl_start_ns"] = 0
    return d


@pytest.mark.parametrize("name", list(REGISTRY))
def test_models_separate_shifted_behaviour(name, tmp_path):
    cols = list("abcd")
    tr = pd.concat([mkdf(synth(150, s), 0, f"r{s}") for s in range(3)], ignore_index=True)
    bad = synth(40, 9); bad["a"] *= 3; bad["c"] += 30
    te = pd.concat([mkdf(synth(80, 7), 0, "t"), mkdf(bad, 1, "t", "burst")], ignore_index=True)
    b = train_bundle(name, tr, cols)
    assert b.t2 >= 1.5 * b.t1 > 0 and b.meta["threshold_source"] == "leave-one-run-out"
    r = evaluate_bundle(b, te)["summary"]
    assert r["roc_auc"] > 0.95 and r["recall"] > 0.8 and r["fpr"] < 0.15
    b.save(tmp_path / "m.joblib")
    b2 = Bundle.load(tmp_path / "m.joblib")
    assert np.allclose(b2.score(te), b.score(te))                      # persistence round-trip
    assert set(b.model.explain(te.iloc[-1:], 2)[0]) & {"a", "c"}       # explanation names the shifted features


def test_event_level_latency():
    from ml.evaluation.detection_eval import event_level
    d = mkdf(synth(6), 1, "r", "cpu_pressure"); d["wl_start_ns"] = 0
    ev = event_level(d, np.array([0, 0, 1, 1, 1, 1], bool), persist=2)
    assert ev.detected.iloc[0] and ev.latency_ms.iloc[0] == 4000.0    # end of 2nd consecutive flagged window
