"""Anomaly scorers: shared result types, robust per-machine statistics, calibration and the IsolationForest candidate.

Language rules (ADR-007, prompt.md §7): scores describe how *unusual* a machine-week is compared with its own
history, never intent. Explanations are factual comparisons ("fuel litres 2.4x this machine's median") and a score
is only exposed in [0, 1] when it has been calibrated against a held-out validation distribution — an uncalibrated
raw score is kept separately and never presented as a probability.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import numpy.typing as npt
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from asseta.ml.datasets import FeatureMatrix, FloatArray

MAD_TO_SIGMA = 1.4826  # MAD of a normal distribution x this = its standard deviation


class Direction(StrEnum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"


@dataclass(frozen=True, slots=True)
class Contribution:
    feature: str
    value: float
    reference: float  # the median the value is compared with
    direction: Direction
    magnitude: float  # robust deviations from the reference (|z|)
    reference_scope: str  # "machine" or "fleet"


@dataclass(frozen=True, slots=True)
class ScoredRow:
    entity_id: str
    as_of: str
    raw_score: float | None  # higher = more unusual; scale is model-specific; None when no feature was present
    score: float | None  # calibrated empirical percentile in [0, 1]; None unless `calibrated`
    calibrated: bool
    contributions: tuple[Contribution, ...]
    explanations: tuple[str, ...]


class CalibrationError(ValueError):
    """Not enough validation scores to calibrate honestly."""


class EmpiricalCalibrator:
    """Maps raw scores to the fraction of validation rows scoring at or below them (empirical CDF).

    The result is a percentile rank against held-out normal-looking weeks, which is monotone and bounded in [0, 1].
    It is *not* a probability that anything is wrong; callers present it as "more unusual than N% of recent weeks".
    """

    MIN_SAMPLES = 20

    def __init__(self, validation_scores: FloatArray) -> None:
        finite = np.sort(validation_scores[np.isfinite(validation_scores)])
        if finite.size < self.MIN_SAMPLES:
            raise CalibrationError(f"{finite.size} validation scores; at least {self.MIN_SAMPLES} required")
        self._reference = finite

    @property
    def n_samples(self) -> int:
        return int(self._reference.size)

    def transform(self, raw: FloatArray) -> FloatArray:
        ranks = np.searchsorted(self._reference, raw, side="right") / self._reference.size
        return np.where(np.isfinite(raw), ranks, np.nan)


@dataclass(frozen=True, eq=False)
class RobustStats:
    """Per-machine (fallback: tenant-wide) median and robust scale per feature, fitted on train rows only.

    The scale is MADx1.4826 floored by 5% of |median| and half the tenant-wide standard deviation, so a feature that
    happens to be constant for one machine (e.g. zero exceptions every week) cannot turn a trivial change into an
    enormous deviation. Machines with fewer than `min_history` train values for a feature use tenant-wide stats.
    """

    feature_codes: tuple[str, ...]
    global_median: FloatArray
    global_scale: FloatArray
    entity_median: dict[str, FloatArray]
    entity_scale: dict[str, FloatArray]

    @classmethod
    def fit(cls, train: FeatureMatrix, min_history: int = 4) -> RobustStats:
        if len(train) == 0:
            raise ValueError("cannot fit on an empty train split")
        x = train.values
        g_med = _nan_to(_safe_nanmedian(x), 0.0)
        g_std = _nan_to(_safe_nanstd(x), 0.0)
        g_mad = _nan_to(_safe_nanmedian(np.abs(x - g_med)), 0.0)
        floor = np.maximum(0.5 * g_std, 1e-3)
        g_scale = np.maximum.reduce([MAD_TO_SIGMA * g_mad, 0.05 * np.abs(g_med), floor])
        ent_med: dict[str, FloatArray] = {}
        ent_scale: dict[str, FloatArray] = {}
        ids = np.array(train.entity_ids)
        for eid in sorted(set(train.entity_ids)):
            ex = x[ids == eid]
            enough = (~np.isnan(ex)).sum(axis=0) >= min_history
            med = np.where(enough, _nan_to(_safe_nanmedian(ex), 0.0), g_med)
            mad = _nan_to(_safe_nanmedian(np.abs(ex - med)), 0.0)
            scale = np.maximum.reduce([MAD_TO_SIGMA * mad, 0.05 * np.abs(med), floor])
            ent_med[eid] = med
            ent_scale[eid] = np.where(enough, scale, g_scale)
        return cls(train.feature_codes, g_med, g_scale, ent_med, ent_scale)

    def reference(self, matrix: FeatureMatrix) -> tuple[FloatArray, FloatArray, npt.NDArray[np.bool_]]:
        n, d = matrix.values.shape
        med, scale = np.empty((n, d)), np.empty((n, d))
        is_entity = np.zeros(n, dtype=np.bool_)
        for i, eid in enumerate(matrix.entity_ids):
            if eid in self.entity_median:
                med[i], scale[i], is_entity[i] = self.entity_median[eid], self.entity_scale[eid], True
            else:
                med[i], scale[i] = self.global_median, self.global_scale
        return med, scale, is_entity

    def zscores(self, matrix: FeatureMatrix) -> FloatArray:
        if matrix.feature_codes != self.feature_codes:
            raise ValueError("matrix feature set differs from the one the model was fitted on")
        med, scale, _ = self.reference(matrix)
        return (matrix.values - med) / scale


def _per_column(x: FloatArray, fn: Callable[[FloatArray], float]) -> FloatArray:
    """Apply `fn` to the finite values of each column; NaN where a column has none (no all-NaN warnings)."""
    out = np.full(x.shape[1], np.nan)
    for j in range(x.shape[1]):
        col = x[:, j][np.isfinite(x[:, j])]
        if col.size:
            out[j] = fn(col)
    return out


def _safe_nanmedian(x: FloatArray) -> FloatArray:
    return _per_column(x, lambda c: float(np.median(c)))


def _safe_nanstd(x: FloatArray) -> FloatArray:
    return _per_column(x, lambda c: float(np.std(c)))


def _nan_to(x: FloatArray, fill: float) -> FloatArray:
    return np.where(np.isfinite(x), x, fill)


def describe(c: Contribution) -> str:
    """Neutral, factual wording; ratios only when the reference is a meaningful positive quantity."""
    label = c.feature.replace("_", " ")
    whose = "this machine's" if c.reference_scope == "machine" else "the fleet's"
    if c.reference > 0 and c.value >= 0:
        ratio = c.value / c.reference
        if ratio >= 1.5 or ratio <= 0.67:
            return f"{label} {ratio:.1f}x {whose} median ({c.value:.4g} vs {c.reference:.4g})"
    side = "above" if c.direction is Direction.ABOVE else "below"
    return f"{label} {c.magnitude:.1f} robust deviations {side} {whose} median ({c.value:.4g} vs {c.reference:.4g})"


class AnomalyScorer(ABC):
    """Common fit/calibrate/score contract for the baseline and the candidate model."""

    name: str
    stats: RobustStats | None = None
    calibrator: EmpiricalCalibrator | None = None

    @abstractmethod
    def fit(self, train: FeatureMatrix) -> AnomalyScorer: ...

    @abstractmethod
    def raw_scores(self, matrix: FeatureMatrix) -> FloatArray:
        """Higher = more unusual; NaN for rows with no feature present."""

    def calibrate(self, validation: FeatureMatrix) -> bool:
        """Fit the empirical CDF on validation scores; returns False (and stays uncalibrated) if too few rows."""
        try:
            self.calibrator = EmpiricalCalibrator(self.raw_scores(validation))
        except CalibrationError:
            self.calibrator = None
        return self.calibrator is not None

    def score(self, matrix: FeatureMatrix, top_k: int = 3) -> list[ScoredRow]:
        stats = self._require_stats()
        raw = self.raw_scores(matrix)
        cal = self.calibrator.transform(raw) if self.calibrator is not None else None
        z = stats.zscores(matrix)
        med, _, is_entity = stats.reference(matrix)
        out: list[ScoredRow] = []
        for i, key in enumerate(matrix.keys):
            contribs = _top_contributions(
                matrix.feature_codes, matrix.values[i], z[i], med[i], bool(is_entity[i]), top_k
            )
            r = float(raw[i])
            finite = math.isfinite(r)
            out.append(
                ScoredRow(
                    entity_id=key.entity_id,
                    as_of=key.as_of.isoformat(),
                    raw_score=r if finite else None,
                    score=float(cal[i]) if cal is not None and finite else None,
                    calibrated=cal is not None and finite,
                    contributions=contribs,
                    explanations=tuple(describe(c) for c in contribs),
                )
            )
        return out

    def _require_stats(self) -> RobustStats:
        if self.stats is None:
            raise RuntimeError(f"{self.name} is not fitted")
        return self.stats


def _top_contributions(
    codes: tuple[str, ...], values: FloatArray, z: FloatArray, med: FloatArray, is_entity: bool, top_k: int
) -> tuple[Contribution, ...]:
    present = [j for j in range(len(codes)) if math.isfinite(z[j])]
    order = sorted(present, key=lambda j: -abs(float(z[j])))[:top_k]
    return tuple(
        Contribution(
            feature=codes[j],
            value=float(values[j]),
            reference=float(med[j]),
            direction=Direction.ABOVE if z[j] >= 0 else Direction.BELOW,
            magnitude=round(float(abs(z[j])), 4),
            reference_scope="machine" if is_entity else "fleet",
        )
        for j in order
    )


class IsolationForestModel(AnomalyScorer):
    """Unsupervised candidate: IsolationForest over per-machine robust deviations, standardized on train only.

    Feeding per-machine deviations (rather than raw litres or hours) lets one forest serve a mixed fleet where a
    40-tonne excavator and a compactor have very different normal values; the forest then learns which *combinations*
    of deviations are rare (e.g. engine hours up while meter hours are flat). Missing values become 0 deviation
    (the machine's own train median). `per_entity_centering=False` uses raw values with train-median imputation.
    Explanations reuse the robust deviations, which approximate — not decompose — the forest's decision.
    """

    name = "isolation_forest"

    def __init__(
        self,
        random_state: int = 0,
        contamination: float | str = "auto",
        n_estimators: int = 200,
        per_entity_centering: bool = True,
    ) -> None:
        self.random_state = random_state
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.per_entity_centering = per_entity_centering
        self.scaler: StandardScaler | None = None
        self.forest: IsolationForest | None = None

    def _design(self, matrix: FeatureMatrix) -> FloatArray:
        stats = self._require_stats()
        if self.per_entity_centering:
            return np.nan_to_num(stats.zscores(matrix), nan=0.0)
        return np.where(np.isnan(matrix.values), stats.global_median, matrix.values)

    def fit(self, train: FeatureMatrix) -> IsolationForestModel:
        self.stats = RobustStats.fit(train)
        design = self._design(train)
        self.scaler = StandardScaler().fit(design)
        self.forest = IsolationForest(
            n_estimators=self.n_estimators, contamination=self.contamination, random_state=self.random_state
        ).fit(self.scaler.transform(design))
        return self

    def raw_scores(self, matrix: FeatureMatrix) -> FloatArray:
        if self.forest is None or self.scaler is None:
            raise RuntimeError("isolation_forest is not fitted")
        raw = -np.asarray(self.forest.score_samples(self.scaler.transform(self._design(matrix))), dtype=np.float64)
        return np.where(np.isnan(matrix.values).all(axis=1), np.nan, raw)
