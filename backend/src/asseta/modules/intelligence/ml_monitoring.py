"""Drift and latency monitoring per deployed model version (ADR-007 "Model lifecycle", Gate 6D).

* Drift: PSI per feature (`asseta.ml.drift.feature_drift`) between the model's training window (the train split of
  its manifest) and the most recent four weeks of snapshots after that window (same snapshot source as training).
  Each computation is one append-only `model_drift` row. A summary level of DRIFT, when the previous row was not
  DRIFT, publishes `MlModelDriftDetected` (platform notification to `platform.ml.read`) and is audited.
* Latency and volume: p50/p95 of `inference_audit.latency_ms` over the model's recent OK runs, outcome counts, and
  prediction counts by decision state — read on the platform model detail.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from asseta.core.audit import AuditService
from asseta.core.db import DbScope, apply_scope
from asseta.core.outbox import OutboxWriter
from asseta.ml.datasets import build_matrix
from asseta.ml.drift import DriftLevel, DriftReport, feature_drift
from asseta.ml.features import R1_FEATURES
from asseta.modules.intelligence.feature_store import load_snapshot_rows
from asseta.modules.intelligence.linking import SYSTEM_ACTOR, TOPIC
from asseta.modules.intelligence.ml_models import DEPLOYED_STATUSES, SOURCE_OBSERVED, ModelVersion
from asseta.modules.intelligence.ml_monitoring_models import (
    DriftSummaryLevel,
    InferenceAudit,
    InferenceOutcome,
    ModelDrift,
    Prediction,
)
from asseta.modules.intelligence.ml_training import clean_json

log = structlog.get_logger()

RECENT_WINDOW = timedelta(weeks=4)
DRIFT_EVERY = timedelta(hours=20)  # at most one drift computation per model per day
LATENCY_SAMPLE = 200  # most recent OK runs used for p50/p95


def _iso(value: Any) -> datetime | None:
    return datetime.fromisoformat(value) if isinstance(value, str) and value else None


def _empty(reason: str) -> DriftReport:
    return DriftReport((), DriftLevel.INSUFFICIENT_DATA, reason)


def compute_drift(session: Session, model: ModelVersion, now: datetime) -> ModelDrift:
    """One drift row for a model (caller: platform/system scope; snapshots are read in the tenant's scope)."""
    splits = model.manifest.get("splits") or {}
    train = splits.get("train") or {}
    train_start, train_end = _iso(train.get("start")), _iso(train.get("end"))
    source = str(model.manifest.get("snapshot_source") or SOURCE_OBSERVED)
    recent_start = recent_end = None
    n_train = n_recent = 0
    if train_start is None or train_end is None:
        report = _empty("The model manifest has no training window.")
    else:
        train_rows = load_snapshot_rows(
            session, model.tenant_id, train_start - timedelta(microseconds=1), train_end, R1_FEATURES, source
        )
        recent_all = load_snapshot_rows(session, model.tenant_id, train_end, now, R1_FEATURES, source)
        recent_end = max((s.as_of for _, s in recent_all), default=None)
        recent_start = max(train_end, recent_end - RECENT_WINDOW) if recent_end else None
        recent_rows = [(i, s) for i, s in recent_all if recent_start is not None and s.as_of > recent_start]
        if not train_rows or not recent_rows:
            report = _empty("No snapshots after the training window yet; drift is measured once new weeks arrive.")
        else:
            train_m = build_matrix([s for _, s in train_rows], R1_FEATURES)
            recent_m = build_matrix([s for _, s in recent_rows], R1_FEATURES)
            n_train, n_recent = len(train_m), len(recent_m)
            report = feature_drift(train_m, recent_m)
    row = ModelDrift(
        id=uuid.uuid4(),
        tenant_id=model.tenant_id,
        model_version_id=model.id,
        computed_at=now,
        train_start=train_start,
        train_end=train_end,
        recent_start=recent_start,
        recent_end=recent_end,
        n_train=n_train,
        n_recent=n_recent,
        features=[
            clean_json(
                {
                    "feature": f.feature,
                    "psi": f.psi,
                    "level": f.level.value,
                    "n_expected": f.n_expected,
                    "n_actual": f.n_actual,
                }
            )
            for f in report.features
        ],
        level=DriftSummaryLevel(report.level.value),
        summary=report.summary,
    )
    previous = session.execute(
        select(ModelDrift.level)
        .where(ModelDrift.model_version_id == model.id)
        .order_by(ModelDrift.computed_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    session.add(row)
    session.flush()
    if row.level is DriftSummaryLevel.DRIFT and previous is not DriftSummaryLevel.DRIFT:
        _announce(session, model, row)
    return row


def _announce(session: Session, model: ModelVersion, row: ModelDrift) -> None:
    drifted = [f["feature"] for f in row.features if f.get("level") == "DRIFT"]
    payload = {
        "model_version_id": str(model.id),
        "drift_id": str(row.id),
        "name": model.name,
        "version": model.version,
        "level": row.level.value,
        "features": drifted,
        "summary": row.summary,
    }
    OutboxWriter(session).emit(
        topic=TOPIC, event_type="MlModelDriftDetected", key=str(model.id), payload=payload, tenant_id=model.tenant_id
    )
    AuditService(session).record(
        actor=SYSTEM_ACTOR,
        action="platform.ml.drift.detected",
        entity_type="model_version",
        entity_id=model.id,
        tenant_id=model.tenant_id,
        after=payload,
    )


def run_drift_cycle(sm: sessionmaker[Session], now: datetime, *, force: bool = False) -> list[ModelDrift]:
    """Drift for every deployed model not measured in the last `DRIFT_EVERY` (all when `force`). Never raises."""
    out: list[ModelDrift] = []
    try:
        with sm.begin() as s:
            apply_scope(s, DbScope.SYSTEM, None, None)
            ids = list(s.execute(select(ModelVersion.id).where(ModelVersion.status.in_(DEPLOYED_STATUSES))).scalars())
    except Exception:
        log.exception("ml_drift_cycle_failed")
        return out
    for model_id in ids:
        try:
            with sm.begin() as s:
                apply_scope(s, DbScope.SYSTEM, None, None)
                last = s.execute(
                    select(func.max(ModelDrift.computed_at)).where(ModelDrift.model_version_id == model_id)
                ).scalar_one_or_none()
                if not force and last is not None and now - last < DRIFT_EVERY:
                    continue
                model = s.execute(select(ModelVersion).where(ModelVersion.id == model_id)).scalar_one()
                out.append(compute_drift(s, model, now))
        except Exception:
            log.exception("ml_drift_failed", model_version_id=str(model_id))
    return out


@dataclass(frozen=True)
class MonitoringStats:
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    runs_by_outcome: dict[str, int]
    predictions_by_state: dict[str, int]
    last_inference_at: datetime | None
    last_error: str | None


def monitoring_stats(session: Session, model_id: uuid.UUID) -> MonitoringStats:
    recent_ok = (
        select(InferenceAudit.latency_ms)
        .where(InferenceAudit.model_version_id == model_id, InferenceAudit.outcome == InferenceOutcome.OK)
        .order_by(InferenceAudit.started_at.desc())
        .limit(LATENCY_SAMPLE)
        .subquery()
    )
    p50, p95 = session.execute(
        select(
            func.percentile_cont(0.5).within_group(recent_ok.c.latency_ms),
            func.percentile_cont(0.95).within_group(recent_ok.c.latency_ms),
        )
    ).one()
    outcomes = dict(
        session.execute(
            select(InferenceAudit.outcome, func.count())
            .where(InferenceAudit.model_version_id == model_id)
            .group_by(InferenceAudit.outcome)
        )
        .tuples()
        .all()
    )
    states = dict(
        session.execute(
            select(Prediction.decision_state, func.count())
            .where(Prediction.model_version_id == model_id)
            .group_by(Prediction.decision_state)
        )
        .tuples()
        .all()
    )
    last = session.execute(
        select(InferenceAudit.started_at, InferenceAudit.outcome, InferenceAudit.reason)
        .where(InferenceAudit.model_version_id == model_id)
        .order_by(InferenceAudit.started_at.desc(), InferenceAudit.created_at.desc())
        .limit(1)
    ).first()
    return MonitoringStats(
        latency_p50_ms=None if p50 is None else float(p50),
        latency_p95_ms=None if p95 is None else float(p95),
        runs_by_outcome={k.value: int(v) for k, v in outcomes.items()},
        predictions_by_state={k.value: int(v) for k, v in states.items()},
        last_inference_at=last[0] if last else None,
        last_error=last[2] if last and last[1] is InferenceOutcome.ERROR else None,
    )
