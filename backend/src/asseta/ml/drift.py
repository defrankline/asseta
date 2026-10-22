"""Population Stability Index per feature between the training window and a recent window.

Bins are quantiles of the *training* distribution (so each training bin holds roughly equal mass), plus a dedicated
bin for missing values: a feature that suddenly goes missing (tracker offline, capture app change) is drift too.
Conventional thresholds: PSI < 0.1 stable, 0.1-0.25 watch, >= 0.25 drift.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from asseta.ml.datasets import FeatureMatrix, FloatArray

PSI_WATCH = 0.1
PSI_DRIFT = 0.25
_EPS = 1e-4  # smoothing so empty bins do not produce infinite PSI


class DriftLevel(StrEnum):
    STABLE = "STABLE"
    WATCH = "WATCH"
    DRIFT = "DRIFT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


def _bin_shares(values: FloatArray, edges: FloatArray) -> FloatArray:
    missing = ~np.isfinite(values)
    finite = values[~missing]
    # interior edges only: values below the first / above the last quantile fall into the outer bins
    idx = np.searchsorted(edges[1:-1], finite, side="right")
    counts = np.bincount(idx, minlength=len(edges) - 1).astype(np.float64)
    counts = np.append(counts, float(missing.sum()))
    return np.asarray(counts / max(values.size, 1), dtype=np.float64)


def psi(expected: FloatArray, actual: FloatArray, bins: int = 10) -> float:
    """PSI of `actual` against `expected`; quantile bins from `expected`, plus one missing-value bin."""
    exp_finite = expected[np.isfinite(expected)]
    if exp_finite.size == 0:
        edges = np.array([-np.inf, np.inf])
    else:
        quantiles = np.quantile(exp_finite, np.linspace(0, 1, bins + 1))
        edges = np.unique(np.concatenate([[-np.inf], quantiles[1:-1], [np.inf]]))
    e = _bin_shares(expected, edges) + _EPS
    a = _bin_shares(actual, edges) + _EPS
    return float(np.sum((a - e) * np.log(a / e)))


def level_for(value: float | None) -> DriftLevel:
    if value is None or math.isnan(value):
        return DriftLevel.INSUFFICIENT_DATA
    if value >= PSI_DRIFT:
        return DriftLevel.DRIFT
    if value >= PSI_WATCH:
        return DriftLevel.WATCH
    return DriftLevel.STABLE


@dataclass(frozen=True, slots=True)
class FeatureDrift:
    feature: str
    psi: float | None
    level: DriftLevel
    n_expected: int
    n_actual: int


@dataclass(frozen=True, slots=True)
class DriftReport:
    features: tuple[FeatureDrift, ...]
    level: DriftLevel  # worst feature level (INSUFFICIENT_DATA only if no feature could be measured)
    summary: str


def feature_drift(train: FeatureMatrix, recent: FeatureMatrix, bins: int = 10, min_samples: int = 30) -> DriftReport:
    if train.feature_codes != recent.feature_codes:
        raise ValueError("train and recent windows must share a feature set")
    if train.tenant_id != recent.tenant_id:
        raise ValueError("drift is measured within one tenant")
    out: list[FeatureDrift] = []
    for j, code in enumerate(train.feature_codes):
        e, a = train.values[:, j], recent.values[:, j]
        value = psi(e, a, bins) if e.size >= min_samples and a.size >= min_samples else None
        out.append(FeatureDrift(code, value, level_for(value), int(e.size), int(a.size)))
    measured = [f for f in out if f.level is not DriftLevel.INSUFFICIENT_DATA]
    order = [DriftLevel.STABLE, DriftLevel.WATCH, DriftLevel.DRIFT]
    worst = max((f.level for f in measured), key=order.index, default=DriftLevel.INSUFFICIENT_DATA)
    drifted = [f.feature for f in measured if f.level is DriftLevel.DRIFT]
    watch = [f.feature for f in measured if f.level is DriftLevel.WATCH]
    if not measured:
        summary = f"Not enough rows to measure drift (need {min_samples} per window)."
    else:
        summary = (
            f"{len(measured)} features measured: {len(drifted)} drifted"
            + (f" ({', '.join(drifted)})" if drifted else "")
            + f", {len(watch)} to watch"
            + (f" ({', '.join(watch)})" if watch else "")
            + "."
        )
    return DriftReport(tuple(out), worst, summary)
