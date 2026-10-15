import numpy as np
import pandas as pd

from ml.statistical.baseline import RobustZBaseline
from ml.evaluation.metrics import detection_metrics


def test_baseline_separates_obvious_anomalies():
    rng = np.random.default_rng(0)
    normal = pd.DataFrame({"x": rng.normal(10, 1, 400), "y": rng.normal(5, 0.5, 400)})
    bad = pd.DataFrame({"x": rng.normal(30, 1, 40), "y": rng.normal(5, 0.5, 40)})
    m = RobustZBaseline(top_k=1, quantile=0.99).fit(normal, ["x", "y"])
    df = pd.concat([normal.iloc[:100], bad], ignore_index=True)
    y = np.r_[np.zeros(100), np.ones(40)]
    r = detection_metrics(y, m.score(df), m.threshold)
    assert r["recall"] > 0.95 and r["fpr"] < 0.05 and r["roc_auc"] > 0.99
    assert m.explain(bad.iloc[:1], 1)[0] == ["x"]


def test_metrics_formulas():
    r = detection_metrics([1, 1, 0, 0], [0.9, 0.2, 0.8, 0.1], 0.5)
    assert (r["tp"], r["fn"], r["fp"], r["tn"]) == (1, 1, 1, 1)
    assert r["precision"] == 0.5 and r["recall"] == 0.5 and r["f1"] == 0.5 and r["fpr"] == 0.5
