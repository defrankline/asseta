import json
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from asseta.ml.datasets import (
    FeatureMatrix,
    ReadinessStatus,
    RowKey,
    SplitConfig,
    SufficiencyCriteria,
    TenantMixingError,
    assess_readiness,
    build_manifest,
    build_matrix,
    temporal_split,
)
from asseta.ml.features import R1_FEATURES, FeatureEntity, FeatureSnapshot

T0 = datetime(2026, 1, 5, tzinfo=UTC)


def snap(
    tenant: str, entity: str, code: str, as_of: datetime, value: float | None, version: int = 1
) -> FeatureSnapshot:
    return FeatureSnapshot(tenant, FeatureEntity.MACHINE, entity, code, version, as_of, "7d", value, as_of, 1)


def matrix(n_machines: int, n_periods: int, step: timedelta = timedelta(days=7), seed: int = 0) -> FeatureMatrix:
    rng = np.random.default_rng(seed)
    keys = tuple(RowKey(T0 + step * p, f"M{m}") for p in range(n_periods) for m in range(n_machines))
    codes = R1_FEATURES.codes
    return FeatureMatrix("t1", codes, keys, rng.normal(10, 1, (len(keys), len(codes))))


def test_mixed_tenants_are_refused() -> None:
    with pytest.raises(TenantMixingError):
        build_matrix([snap("t1", "M1", "fuel_litres", T0, 1.0), snap("t2", "M2", "fuel_litres", T0, 1.0)], R1_FEATURES)


def test_build_matrix_pivots_and_rejects_stale_versions_and_duplicates() -> None:
    m = build_matrix([snap("t1", "M1", "fuel_litres", T0, 5.0), snap("t1", "M1", "meter_hours", T0, None)], R1_FEATURES)
    assert len(m) == 1 and m.column("fuel_litres")[0] == 5.0
    assert np.isnan(m.column("meter_hours")[0]) and np.isnan(m.column("expense_total")[0])
    with pytest.raises(ValueError, match="version"):
        build_matrix([snap("t1", "M1", "fuel_litres", T0, 1.0, version=2)], R1_FEATURES)
    with pytest.raises(ValueError, match="duplicate"):
        build_matrix([snap("t1", "M1", "fuel_litres", T0, 1.0)] * 2, R1_FEATURES)


def test_temporal_split_purges_overlapping_windows_no_entity_time_leakage() -> None:
    m = matrix(4, 60, step=timedelta(days=1))  # daily as_of with 7-day windows: neighbours overlap
    cfg = SplitConfig(T0 + timedelta(days=30), T0 + timedelta(days=45), purge=timedelta(days=7))
    s = temporal_split(m, cfg)
    assert s.purged_rows == 2 * 6 * 4  # six overlapping days after each boundary, four machines
    assert len(s.train) + len(s.validation) + len(s.test) + s.purged_rows == len(m)
    for eid in {"M0", "M1", "M2", "M3"}:
        tr = [k.as_of for k in s.train.keys if k.entity_id == eid]
        va = [k.as_of for k in s.validation.keys if k.entity_id == eid]
        te = [k.as_of for k in s.test.keys if k.entity_id == eid]
        assert max(tr) <= min(va) - cfg.purge  # no validation window reaches back into train time
        assert max(va) <= min(te) - cfg.purge


def test_readiness_insufficient_then_ready() -> None:
    criteria = SufficiencyCriteria(min_machines=5, min_machine_weeks=40, min_weeks_history=8)
    small = assess_readiness(matrix(3, 6), criteria)
    assert small.status is ReadinessStatus.INSUFFICIENT_DATA
    assert len(small.reasons) == 3 and "at least 5 required" in small.reasons[0]
    assert assess_readiness(None, criteria).status is ReadinessStatus.INSUFFICIENT_DATA
    big = matrix(5, 8)
    ok = assess_readiness(big, criteria)
    assert ok.ready and ok.reasons == () and ok.observed["machine_weeks"] == 40
    # rows that are mostly missing do not count
    sparse = big.with_values(np.where(np.arange(big.values.shape[1]) < 10, np.nan, big.values))
    assert not assess_readiness(sparse, criteria).ready


def test_manifest_is_json_serialisable_and_content_hash_tracks_data() -> None:
    m = matrix(5, 10)
    s = temporal_split(m, SplitConfig(T0 + timedelta(days=35), T0 + timedelta(days=49), timedelta(days=7)))
    man = build_manifest(m, s, R1_FEATURES.feature_set_hash())
    d = json.loads(man.to_json())
    assert d["tenant_id"] == "t1" and d["feature_set_hash"] == R1_FEATURES.feature_set_hash()
    assert d["splits"]["train"]["rows"] == 30 and d["splits"]["test"]["entities"] == 5
    assert "NaN" in d["missing_value_policy"]
    assert m.content_hash() == matrix(5, 10).content_hash()
    assert m.content_hash() != matrix(5, 10, seed=1).content_hash()
