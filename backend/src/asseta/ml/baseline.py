"""Statistical baseline (robust z-score per machine) and the R1 baseline insights (ADR-007 "Baseline insights").

The baseline is what any learned model must beat before it may leave shadow mode: it is transparent (median and
MAD of the machine's own history), needs little data and is easy to explain to an owner. Insights return
`INSUFFICIENT_DATA` with the minimum history they need rather than a number computed from too little evidence.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from asseta.ml.datasets import FeatureMatrix, FloatArray, ReadinessStatus
from asseta.ml.models import AnomalyScorer, RobustStats


class RobustZScoreBaseline(AnomalyScorer):
    """Score = the largest robust deviation of any present feature from the machine's own train median.

    max |z| (rather than a sum) keeps the explanation honest: the score is literally "how far the most unusual
    feature is from normal", and the top contribution is that feature.
    """

    name = "robust_zscore"

    def __init__(self, min_history: int = 4) -> None:
        self.min_history = min_history

    def fit(self, train: FeatureMatrix) -> RobustZScoreBaseline:
        self.stats = RobustStats.fit(train, min_history=self.min_history)
        return self

    def raw_scores(self, matrix: FeatureMatrix) -> FloatArray:
        az = np.abs(self._require_stats().zscores(matrix))
        present = np.isfinite(az).any(axis=1)
        out = np.full(len(matrix), np.nan)
        out[present] = np.nanmax(az[present], axis=1)
        return out


# --- Baseline insights -----------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Insight:
    code: str
    status: ReadinessStatus
    value: float | None
    reference: float | None
    unit: str
    message: str
    min_required: int
    observed: int


def _insufficient(code: str, unit: str, observed: int, min_required: int, what: str) -> Insight:
    return Insight(
        code,
        ReadinessStatus.INSUFFICIENT_DATA,
        None,
        None,
        unit,
        f"{observed} {what} available; at least {min_required} needed for an honest comparison.",
        min_required,
        observed,
    )


def fuel_efficiency_insight(history: Sequence[float | None], current: float | None, min_weeks: int = 4) -> Insight:
    """Current litres per meter hour vs the median of the machine's own previous weeks."""
    past = [v for v in history if v is not None and math.isfinite(v)]
    if current is None or len(past) < min_weeks:
        return _insufficient("FUEL_EFFICIENCY", "l/h", len(past), min_weeks, "weeks of fuel and meter history")
    ref = statistics.median(past)
    msg = (
        f"{current:.2f} l/h this week vs a median of {ref:.2f} l/h ({current / ref:.1f}x)"
        if ref > 0
        else f"{current:.2f} l/h this week; no fuel use recorded in previous weeks"
    )
    return Insight("FUEL_EFFICIENCY", ReadinessStatus.READY, current, ref, "l/h", msg, min_weeks, len(past))


def utilization_insight(hours_per_week: Sequence[float | None], available_days: int, min_weeks: int = 4) -> Insight:
    """Average meter (or engine) hours per available day over the observed weeks."""
    weeks = [v for v in hours_per_week if v is not None and math.isfinite(v)]
    if len(weeks) < min_weeks or available_days <= 0:
        return _insufficient("UTILIZATION", "h/day", len(weeks), min_weeks, "weeks of meter history")
    value = sum(weeks) / available_days
    return Insight(
        "UTILIZATION",
        ReadinessStatus.READY,
        value,
        None,
        "h/day",
        f"{value:.1f} hours per available day over {len(weeks)} weeks",
        min_weeks,
        len(weeks),
    )


def cashflow_trend_insight(weekly_net: Sequence[float], min_weeks: int = 6) -> Insight:
    """Least-squares slope of (verified receipts - approved expenses) per week; positive = improving."""
    if len(weekly_net) < min_weeks:
        return _insufficient("CASHFLOW_TREND", "per week", len(weekly_net), min_weeks, "weeks of cash history")
    x = np.arange(len(weekly_net), dtype=np.float64)
    slope = float(np.polyfit(x, np.asarray(weekly_net, dtype=np.float64), 1)[0])
    direction = "improving" if slope > 0 else "declining" if slope < 0 else "flat"
    return Insight(
        "CASHFLOW_TREND",
        ReadinessStatus.READY,
        slope,
        float(statistics.median(weekly_net)),
        "per week",
        f"weekly net cash {direction} by {abs(slope):.2f} per week over {len(weekly_net)} weeks",
        min_weeks,
        len(weekly_net),
    )


def robust_band(values: Sequence[float], k: float = 3.0, min_relative: float = 0.15) -> tuple[float, float, float]:
    """(median, low, high): median +/- max(k x MAD x 1.4826, min_relative x |median|) of a machine's own history.

    The relative floor keeps a very steady machine from being flagged for an ordinary few-percent change."""
    if not values:
        raise ValueError("robust_band needs at least one value")
    med = statistics.median(values)
    mad = statistics.median(abs(v - med) for v in values)
    half = max(k * 1.4826 * mad, min_relative * abs(med))
    return med, med - half, med + half


def weekly_trend(values: Sequence[float]) -> float:
    """Least-squares slope per week (0.0 for fewer than two points)."""
    if len(values) < 2:
        return 0.0
    x = np.arange(len(values), dtype=np.float64)
    return float(np.polyfit(x, np.asarray(values, dtype=np.float64), 1)[0])
