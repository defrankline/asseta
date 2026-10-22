"""Per-tenant training matrices, leakage-safe temporal splits, manifests and data-sufficiency checks.

Why the rules here are strict:

* **Tenant isolation** (prompt.md §7): cross-tenant pooled training is OFF, so building a matrix from snapshots of
  more than one tenant is an error, not a warning.
* **Temporal + grouped split**: rows are machine-weeks. A week-window row computed shortly after the train boundary
  re-uses facts that already sit in the last train rows of the *same machine*, so rows whose feature window straddles
  a boundary are purged rather than assigned. Every machine can appear in every split (per-machine baselines need
  that), but no machine contributes overlapping evidence to two splits.
* **Missing values** stay `NaN` in the matrix. Nothing is imputed here, so the manifest describes the data as
  observed; models impute with statistics fitted on the train split only (see `models.py`). Rows with fewer than
  `SufficiencyCriteria.min_present_fraction` features present do not count toward readiness.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

import numpy as np
import numpy.typing as npt

from asseta.ml.features import FeatureRegistry, FeatureSnapshot

FloatArray = npt.NDArray[np.float64]

MISSING_VALUE_POLICY = (
    "Missing feature values are kept as NaN in the dataset; models impute per-feature medians fitted on the train "
    "split only (per machine when the machine has train history, otherwise tenant-wide)."
)


class TenantMixingError(ValueError):
    """Raised when snapshots from more than one tenant reach one dataset (pooled training is OFF)."""


@dataclass(frozen=True, slots=True, order=True)
class RowKey:
    as_of: datetime
    entity_id: str


@dataclass(frozen=True, eq=False)
class FeatureMatrix:
    """Rows = (machine, as_of), columns = feature codes in registry order; NaN means missing."""

    tenant_id: str
    feature_codes: tuple[str, ...]
    keys: tuple[RowKey, ...]
    values: FloatArray

    def __post_init__(self) -> None:
        if self.values.shape != (len(self.keys), len(self.feature_codes)):
            raise ValueError("values shape must be (rows, features)")

    def __len__(self) -> int:
        return len(self.keys)

    @property
    def entity_ids(self) -> tuple[str, ...]:
        return tuple(k.entity_id for k in self.keys)

    def take(self, index: Sequence[int] | npt.NDArray[np.bool_] | npt.NDArray[np.intp]) -> FeatureMatrix:
        idx = np.flatnonzero(index) if np.asarray(index).dtype == np.bool_ else np.asarray(index, dtype=np.intp)
        return FeatureMatrix(
            self.tenant_id, self.feature_codes, tuple(self.keys[i] for i in idx), self.values[idx].copy()
        )

    def with_values(self, values: FloatArray) -> FeatureMatrix:
        return FeatureMatrix(self.tenant_id, self.feature_codes, self.keys, values)

    def column(self, code: str) -> FloatArray:
        return self.values[:, self.feature_codes.index(code)]

    def present_fraction(self) -> FloatArray:
        if not self.feature_codes:
            return np.zeros(len(self.keys))
        return np.asarray(1.0 - np.isnan(self.values).mean(axis=1), dtype=np.float64)

    def content_hash(self) -> str:
        """sha256 over columns, row keys and values (NaN canonicalised) — identifies the exact training data."""
        h = hashlib.sha256()
        h.update("\x1f".join(self.feature_codes).encode())
        for k in self.keys:
            h.update(f"{k.entity_id}\x1f{k.as_of.isoformat()}\n".encode())
        mask = np.isnan(self.values)
        h.update(np.ascontiguousarray(mask).tobytes())
        h.update(np.ascontiguousarray(np.where(mask, 0.0, np.round(self.values, 9))).tobytes())
        return h.hexdigest()


def build_matrix(snapshots: Iterable[FeatureSnapshot], registry: FeatureRegistry) -> FeatureMatrix:
    """Pivot snapshots into a single-tenant matrix; rejects mixed tenants, unknown or stale feature versions."""
    snaps = list(snapshots)
    tenants = {s.tenant_id for s in snaps}
    if len(tenants) > 1:
        raise TenantMixingError(f"snapshots span {len(tenants)} tenants; cross-tenant pooling is disabled")
    if not tenants:
        raise ValueError("no snapshots")
    codes = registry.codes
    col = {c: i for i, c in enumerate(codes)}
    rows: dict[RowKey, list[float]] = {}
    seen: set[tuple[RowKey, str]] = set()
    for s in snaps:
        if s.feature_code not in col:
            raise ValueError(f"feature {s.feature_code!r} is not in the feature set")
        if s.feature_version != registry.get(s.feature_code).version:
            raise ValueError(f"{s.feature_code}@{s.feature_version} does not match the feature set version")
        key = RowKey(s.as_of, s.entity_id)
        if (key, s.feature_code) in seen:
            raise ValueError(f"duplicate snapshot for {s.entity_id} {s.feature_code} at {s.as_of.isoformat()}")
        seen.add((key, s.feature_code))
        row = rows.setdefault(key, [float("nan")] * len(codes))
        row[col[s.feature_code]] = float("nan") if s.value is None else s.value
    keys = tuple(sorted(rows))
    values = np.array([rows[k] for k in keys], dtype=np.float64).reshape(len(keys), len(codes))
    return FeatureMatrix(tenants.pop(), codes, keys, values)


# --- Temporal split --------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SplitConfig:
    """train: as_of <= train_end; validation: window starts >= train_end and as_of <= validation_end; test: after.

    `purge` should be the longest feature window: a row is only placed after a boundary when its whole window is.
    """

    train_end: datetime
    validation_end: datetime
    purge: timedelta

    def __post_init__(self) -> None:
        if self.validation_end <= self.train_end:
            raise ValueError("validation_end must be after train_end")


def default_split_config(
    matrix: FeatureMatrix, purge: timedelta, train_fraction: float = 0.6, validation_fraction: float = 0.2
) -> SplitConfig:
    """Place boundaries on distinct as_of dates so roughly the given fractions of periods land in each split."""
    dates = sorted({k.as_of for k in matrix.keys})
    if len(dates) < 3:
        raise ValueError("need at least three distinct as_of dates to split")
    t1 = dates[max(0, min(len(dates) - 3, int(len(dates) * train_fraction) - 1))]
    t2_idx = max(dates.index(t1) + 1, int(len(dates) * (train_fraction + validation_fraction)) - 1)
    return SplitConfig(train_end=t1, validation_end=dates[min(t2_idx, len(dates) - 2)], purge=purge)


@dataclass(frozen=True, eq=False)
class DatasetSplit:
    train: FeatureMatrix
    validation: FeatureMatrix
    test: FeatureMatrix
    config: SplitConfig
    purged_rows: int


def temporal_split(matrix: FeatureMatrix, config: SplitConfig) -> DatasetSplit:
    assign = np.full(len(matrix), -1, dtype=np.int8)  # 0 train, 1 validation, 2 test, -1 purged
    for i, k in enumerate(matrix.keys):
        window_start = k.as_of - config.purge
        if k.as_of <= config.train_end:
            assign[i] = 0
        elif window_start >= config.train_end and k.as_of <= config.validation_end:
            assign[i] = 1
        elif window_start >= config.validation_end:
            assign[i] = 2
    return DatasetSplit(
        train=matrix.take(assign == 0),
        validation=matrix.take(assign == 1),
        test=matrix.take(assign == 2),
        config=config,
        purged_rows=int((assign == -1).sum()),
    )


# --- Readiness -------------------------------------------------------------------------------------------------------


class ReadinessStatus(StrEnum):
    READY = "READY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True, slots=True)
class SufficiencyCriteria:
    """Minimum history before an anomaly model may be trained for a tenant (overridable per policy).

    Defaults: 5 machines so per-tenant statistics are not one machine's quirks; 80 usable machine-weeks so the
    IsolationForest sees enough normal variety; 8 weeks so weekly patterns repeat; and enough validation/test rows
    for calibration and evaluation to mean something.
    """

    min_machines: int = 5
    min_machine_weeks: int = 80
    min_weeks_history: int = 8
    min_present_fraction: float = 0.5
    min_validation_rows: int = 20
    min_test_rows: int = 20


@dataclass(frozen=True, slots=True)
class Readiness:
    status: ReadinessStatus
    reasons: tuple[str, ...]
    observed: Mapping[str, float]
    criteria: SufficiencyCriteria

    @property
    def ready(self) -> bool:
        return self.status is ReadinessStatus.READY


def assess_readiness(
    matrix: FeatureMatrix | None, criteria: SufficiencyCriteria, split: DatasetSplit | None = None
) -> Readiness:
    """READY only when every minimum is met; otherwise each unmet minimum is a human-readable reason."""
    if matrix is None or len(matrix) == 0:
        return Readiness(
            ReadinessStatus.INSUFFICIENT_DATA,
            ("No feature history yet; anomaly scoring starts once machines accumulate observed weeks.",),
            {"machines": 0, "machine_weeks": 0, "weeks_history": 0},
            criteria,
        )
    usable = matrix.take(matrix.present_fraction() >= criteria.min_present_fraction)
    machines = len(set(usable.entity_ids))
    machine_weeks = len({(k.entity_id, *k.as_of.isocalendar()[:2]) for k in usable.keys})
    dates = [k.as_of for k in usable.keys]
    weeks = (max(dates) - min(dates)).days / 7 + 1 if dates else 0.0
    observed: dict[str, float] = {"machines": machines, "machine_weeks": machine_weeks, "weeks_history": weeks}
    reasons: list[str] = []
    if machines < criteria.min_machines:
        reasons.append(f"{machines} machines with usable history; at least {criteria.min_machines} required.")
    if machine_weeks < criteria.min_machine_weeks:
        reasons.append(f"{machine_weeks} usable machine-weeks; at least {criteria.min_machine_weeks} required.")
    if weeks < criteria.min_weeks_history:
        reasons.append(f"{weeks:.1f} weeks of history; at least {criteria.min_weeks_history} required.")
    if split is not None:
        observed |= {"validation_rows": len(split.validation), "test_rows": len(split.test)}
        if len(split.validation) < criteria.min_validation_rows:
            reasons.append(
                f"{len(split.validation)} validation rows; at least {criteria.min_validation_rows} required "
                "for calibration."
            )
        if len(split.test) < criteria.min_test_rows:
            reasons.append(f"{len(split.test)} test rows; at least {criteria.min_test_rows} required for evaluation.")
    status = ReadinessStatus.INSUFFICIENT_DATA if reasons else ReadinessStatus.READY
    return Readiness(status, tuple(reasons), observed, criteria)


# --- Manifest --------------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SplitStats:
    rows: int
    entities: int
    start: str | None
    end: str | None

    @classmethod
    def of(cls, m: FeatureMatrix) -> SplitStats:
        dates = [k.as_of for k in m.keys]
        return cls(
            rows=len(m),
            entities=len(set(m.entity_ids)),
            start=min(dates).isoformat() if dates else None,
            end=max(dates).isoformat() if dates else None,
        )


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    """Stored with every MLflow run so a model can always be traced to the exact data and feature versions."""

    tenant_id: str
    feature_set_hash: str
    feature_codes: tuple[str, ...]
    splits: Mapping[str, SplitStats]
    train_end: str
    validation_end: str
    purge_days: float
    purged_rows: int
    content_hash: str
    missing_value_policy: str = MISSING_VALUE_POLICY
    missing_fraction: Mapping[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["feature_codes"] = list(self.feature_codes)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


def build_manifest(matrix: FeatureMatrix, split: DatasetSplit, feature_set_hash: str) -> DatasetManifest:
    missing = np.isnan(matrix.values).mean(axis=0) if len(matrix) else np.zeros(len(matrix.feature_codes))
    return DatasetManifest(
        tenant_id=matrix.tenant_id,
        feature_set_hash=feature_set_hash,
        feature_codes=matrix.feature_codes,
        splits={
            "train": SplitStats.of(split.train),
            "validation": SplitStats.of(split.validation),
            "test": SplitStats.of(split.test),
        },
        train_end=split.config.train_end.isoformat(),
        validation_end=split.config.validation_end.isoformat(),
        purge_days=split.config.purge.total_seconds() / 86400,
        purged_rows=split.purged_rows,
        content_hash=matrix.content_hash(),
        missing_fraction={c: round(float(f), 6) for c, f in zip(matrix.feature_codes, missing, strict=True)},
    )
