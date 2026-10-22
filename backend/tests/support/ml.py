"""Gate 6B/6C helpers: load the synthetic fleet as feature snapshots, run training the way the job does (tenant
scope for reads, platform scope for governance rows) with an in-memory object store and an injectable tracker."""

import dataclasses
import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from asseta.core.audit import AuditActor
from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.ml.evaluation import PromotionCriteria
from asseta.ml.features import FeatureSnapshot
from asseta.ml.synthetic import fleet_snapshots, generate_fleet
from asseta.ml.tracking import ExperimentTracker, NullTracker
from asseta.modules.intelligence.feature_store import store_snapshots, sync_feature_definitions
from asseta.modules.intelligence.inference import InferenceCycleResult, run_inference_cycle
from asseta.modules.intelligence.ml_training import train_tenant
from tests.support.api import Actor
from tests.support.idp import InMemoryObjectStore

LENIENT = PromotionCriteria(min_recall_lift=-1.0, max_alert_rate=1.0, max_recall_std=1.0, min_injected=1)
STRICT = PromotionCriteria(min_recall_lift=1.0)
ACTOR = AuditActor(None, ["system"], "test")


def load_synthetic(tid: str, now: datetime, machines: int = 8, weeks: int = 14, seed: int = 3) -> int:
    fleet = generate_fleet(tenant_id=tid, n_machines=machines, weeks=weeks, seed=seed)
    snaps = [
        dataclasses.replace(s, entity_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{tid}/{s.entity_id}")))
        for s in fleet_snapshots(fleet)
    ]
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, uuid.UUID(tid), None)
        return store_snapshots(s, uuid.UUID(tid), snaps, now, None)


def train(
    tid: str,
    now: datetime,
    promotion: PromotionCriteria | None = None,
    tracker: ExperimentTracker | None = None,
    store: InMemoryObjectStore | None = None,
) -> dict[str, Any]:
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.PLATFORM, None, None)
        sync_feature_definitions(s)
        r = train_tenant(
            s, uuid.UUID(tid), now, store or InMemoryObjectStore(), tracker or NullTracker(), ACTOR, promotion=promotion
        )
        return {
            "readiness": r.readiness.status.value,
            "model_id": str(r.model.id) if r.model else None,
            "passed": r.evaluation.passed if r.evaluation else None,
            "mlflow_run_id": r.model.mlflow_run_id if r.model else None,
            "tracking_note": r.model.tracking_note if r.model else None,
        }


def act(platform: Actor, model_id: str, action: str, reason: str = "Reviewed evaluation", **extra: Any) -> Any:
    return platform.post(f"/api/v1/platform/ml/models/{model_id}/{action}", {"reason": reason, **extra})


def model(platform: Actor, model_id: str) -> dict[str, Any]:
    r = platform.get(f"/api/v1/platform/ml/models/{model_id}")
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


def last_week_end(now: datetime) -> datetime:
    """Most recent Africa/Dar_es_Salaam Monday 00:00 at or before `now` (the tenants' local week end)."""
    local = now.astimezone(ZoneInfo("Africa/Dar_es_Salaam"))
    monday = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday


def fleet_for(
    tid: str, machine_ids: list[str], end: datetime, weeks: int = 14, seed: int = 3, anomaly_rate: float = 0.04
) -> list[FeatureSnapshot]:
    """The synthetic fleet as snapshots of real machines, its last week ending at `end`."""
    start = end - timedelta(weeks=weeks)
    fleet = generate_fleet(tid, len(machine_ids), weeks, seed, start=start, anomaly_rate=anomaly_rate)
    mapping = {f"M{i + 1:03d}": m for i, m in enumerate(machine_ids)}
    return [dataclasses.replace(s, entity_id=mapping[s.entity_id]) for s in fleet_snapshots(fleet)]


def store(tid: str, snaps: list[FeatureSnapshot], now: datetime) -> int:
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, uuid.UUID(tid), None)
        return store_snapshots(s, uuid.UUID(tid), snaps, now, None)


def shifted_week(snaps: list[FeatureSnapshot], weeks: int = 1, **factors: float) -> list[FeatureSnapshot]:
    """Copy the latest week `weeks` weeks later, multiplying the given features (to create unusual weeks)."""
    last = max(s.as_of for s in snaps)
    return [
        dataclasses.replace(
            s,
            as_of=s.as_of + timedelta(weeks=weeks),
            value=None if s.value is None else s.value * factors.get(s.feature_code, 1.0),
        )
        for s in snaps
        if s.as_of == last
    ]


def infer(now: datetime, objects: InMemoryObjectStore, tid: str | None = None) -> InferenceCycleResult:
    return run_inference_cycle(get_sessionmaker(), now, objects, tenant_ids=[uuid.UUID(tid)] if tid else None)
