"""Detection models A/B/C of package section 12 behind one interface.

  A  StatisticalModel        robust z-score (median/MAD) - the baseline
  B  IsolationForestModel    sklearn IsolationForest
  C  AutoencoderModel        feed-forward bottleneck autoencoder (sklearn MLPRegressor, no GPU/torch)

Every model is trained on NORMAL windows only and returns an anomaly score (higher = more anomalous).
Inference is user-space only (the kernel never runs ML)."""
from __future__ import annotations
import numpy as np
import pandas as pd


class Preprocessor:
    """log1p on count-like columns, then robust standardisation, clipped to +-CLIP."""
    CLIP = 10.0

    def fit(self, X: np.ndarray) -> "Preprocessor":
        self.log_cols = X.max(axis=0) > 10.0
        Z = self._log(X)
        self.med = np.median(Z, axis=0)
        mad = np.median(np.abs(Z - self.med), axis=0) * 1.4826
        self.scale = np.maximum.reduce([mad, 0.5 * Z.std(axis=0), 1e-3 * (np.abs(self.med) + 1.0)])
        return self

    def _log(self, X):
        Z = np.array(X, dtype=float, copy=True)
        Z[:, self.log_cols] = np.log1p(np.maximum(Z[:, self.log_cols], 0.0))
        return Z

    def transform(self, X: np.ndarray) -> np.ndarray:
        return np.clip((self._log(X) - self.med) / self.scale, -self.CLIP, self.CLIP)


class BaseModel:
    name = "base"

    def __init__(self, **params):
        self.params = params

    def _X(self, df: pd.DataFrame) -> np.ndarray:
        return df[self.cols].to_numpy(float)

    def fit(self, df: pd.DataFrame, cols: list[str]) -> "BaseModel":
        self.cols = list(cols)
        self._fit(self._X(df))
        return self

    def score(self, df: pd.DataFrame) -> np.ndarray:
        return self._score(self._X(df))

    def explain(self, df: pd.DataFrame, n: int = 3) -> list[list[str]]:
        """Top-n features by standardised deviation (model-agnostic explanation, NFR-09)."""
        Z = np.abs(self.pre.transform(self._X(df)))
        return [[self.cols[j] for j in np.argsort(-r)[:n]] for r in Z]


class StatisticalModel(BaseModel):
    name = "statistical"

    def _fit(self, X):
        self.pre = Preprocessor().fit(X)
        self.top_k = int(self.params.get("top_k", 3))

    def _score(self, X):
        Z = np.abs(self.pre.transform(X))
        k = min(self.top_k, Z.shape[1])
        return np.sort(Z, axis=1)[:, -k:].mean(axis=1)


class IsolationForestModel(BaseModel):
    name = "isolation_forest"

    def _fit(self, X):
        from sklearn.ensemble import IsolationForest
        self.pre = Preprocessor().fit(X)
        p = dict(n_estimators=200, max_samples="auto", contamination="auto", random_state=0, n_jobs=1)
        p.update(self.params)
        self.m = IsolationForest(**p).fit(self.pre.transform(X))

    def _score(self, X):
        return -self.m.score_samples(self.pre.transform(X))


class AutoencoderModel(BaseModel):
    name = "autoencoder"

    def _fit(self, X):
        from sklearn.neural_network import MLPRegressor
        self.pre = Preprocessor().fit(X)
        Z = self.pre.transform(X)
        h = self.params.get("hidden", (24, 16, 8, 16, 24))
        self.m = MLPRegressor(hidden_layer_sizes=h, activation="relu", solver="adam", alpha=1e-4,
                              max_iter=int(self.params.get("max_iter", 300)), random_state=int(self.params.get("seed", 0)),
                              early_stopping=False, tol=1e-5, n_iter_no_change=20)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.m.fit(Z, Z)

    def _score(self, X):
        Z = self.pre.transform(X)
        return ((self.m.predict(Z) - Z) ** 2).mean(axis=1)


REGISTRY = {c.name: c for c in (StatisticalModel, IsolationForestModel, AutoencoderModel)}


def make(name: str, **params) -> BaseModel:
    return REGISTRY[name](**params)
