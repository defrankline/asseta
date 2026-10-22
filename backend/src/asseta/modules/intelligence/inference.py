"""Bounded background inference for deployed anomaly models (ADR-007 "Model predictions", prompt.md §7, Gate 6D).

One cycle (`run_inference_cycle`, called by the intelligence worker after snapshots and on its schedule):

1. The platform hard switch is checked first: when `ml_setting.inference_enabled` is false nothing is scored and one
   `inference_audit` row with outcome SKIPPED records why.
2. For every DEPLOYED_SHADOW / DEPLOYED_ACTIVE model version (a DISABLED, RETIRED or undeployed version never runs)
   the bundle is fetched from object storage, its sha256 verified against the governance record
   (`load_model_bundle`), and the latest feature snapshot per machine (last three weeks, same snapshot source as
   training) is scored. Each machine-week gets one `prediction` row with full provenance.
3. Decision: SHADOW for a shadow deployment (never linked to a case, never visible to tenants); for an ACTIVE
   deployment a calibrated score at or above the evaluation's alert threshold is SURFACED and linked to an
   investigation case through the normal linking (source PREDICTION) with neutral wording; below it,
   BELOW_THRESHOLD; too few features or no calibrated score, INSUFFICIENT_DATA.
4. Every model attempt writes an `inference_audit` row (latency, input rows, OK / SKIPPED / ERROR + reason). Each
   model runs in its own transaction with a time budget (statement timeout + checks between steps); any failure is
   rolled back, recorded as ERROR in a fresh transaction and never propagates — deterministic detection, jobs,
   payments and tracking are unaffected.
"""

import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from asseta.core.db import DbScope, apply_scope
from asseta.core.errors import DependencyUnavailable
from asseta.core.storage import ObjectReader
from asseta.ml.datasets import build_matrix
from asseta.ml.features import R1_FEATURES, FeatureSnapshot
from asseta.ml.models import ScoredRow
from asseta.ml.training import ModelBundle, load_model_bundle
from asseta.modules.fleet.models import Machine
from asseta.modules.intelligence.feature_store import load_snapshot_rows, scoped
from asseta.modules.intelligence.linking import CaseItem, CaseLinker
from asseta.modules.intelligence.ml_lifecycle import inference_enabled
from asseta.modules.intelligence.ml_models import (
    DEPLOYED_STATUSES,
    SOURCE_OBSERVED,
    ModelAction,
    ModelApproval,
    ModelEvaluation,
    ModelStatus,
    ModelVersion,
)
from asseta.modules.intelligence.ml_monitoring_models import DecisionState, InferenceAudit, InferenceOutcome, Prediction
from asseta.modules.intelligence.ml_training import clean_json
from asseta.modules.intelligence.models import CaseSourceType, SignalSeverity, SubjectType
from asseta.modules.policy.service import PolicyService

log = structlog.get_logger()

LOOKBACK = timedelta(weeks=3)  # "latest snapshot" must be at most this old to be scored
MIN_PRESENT_FRACTION = 0.5
DEFAULT_THRESHOLD = 0.98
TENANT_BUDGET_SECONDS = 30.0
BUNDLE_CACHE_SIZE = 8
SWITCH_OFF_REASON = "Inference is switched off platform-wide; no model was run."
PREDICTION_CODE = "ML_UNUSUAL_PATTERN"
SURFACED_TITLE = "Unusual machine-week pattern compared with this machine's history — needs review"
_BUNDLES: "OrderedDict[str, ModelBundle]" = OrderedDict()


class InferenceBudgetExceeded(RuntimeError):
    """The per-tenant time budget ran out between inference steps."""


@dataclass(frozen=True)
class InferenceResult:
    model_version_id: uuid.UUID | None
    tenant_id: uuid.UUID | None
    outcome: InferenceOutcome
    input_rows: int = 0
    written: int = 0
    surfaced: int = 0
    reason: str | None = None


@dataclass
class InferenceCycleResult:
    run_id: uuid.UUID
    switched_off: bool = False
    results: list[InferenceResult] = field(default_factory=list)


def load_bundle(store: ObjectReader, model: ModelVersion) -> ModelBundle:
    """Fetch + verify (sha256) + unpickle; verified bundles are cached by digest (immutable, content-addressed)."""
    cached = _BUNDLES.get(model.artifact_sha256)
    if cached is not None:
        _BUNDLES.move_to_end(model.artifact_sha256)
        return cached
    bundle = load_model_bundle(store.get_bytes(model.artifact_key), model.artifact_sha256)
    if bundle.tenant_id != str(model.tenant_id) or bundle.feature_set_hash != model.feature_set_hash:
        raise ValueError("model artifact does not match the model version's tenant or feature set")
    _BUNDLES[model.artifact_sha256] = bundle
    while len(_BUNDLES) > BUNDLE_CACHE_SIZE:
        _BUNDLES.popitem(last=False)
    return bundle


def clear_bundle_cache() -> None:
    _BUNDLES.clear()


def _audit(
    tenant_id: uuid.UUID | None,
    model_id: uuid.UUID | None,
    run_id: uuid.UUID,
    started_at: datetime,
    started: float,
    outcome: InferenceOutcome,
    reason: str | None,
    input_rows: int = 0,
    written: int = 0,
    surfaced: int = 0,
) -> InferenceAudit:
    return InferenceAudit(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        model_version_id=model_id,
        inference_run_id=run_id,
        started_at=started_at,
        latency_ms=max(0, round((time.monotonic() - started) * 1000)),
        input_rows=input_rows,
        predictions_written=written,
        surfaced=surfaced,
        outcome=outcome,
        reason=reason,
        created_at=started_at,
    )


def _latest_per_machine(
    session: Session, model: ModelVersion, now: datetime, source: str
) -> list[tuple[uuid.UUID, FeatureSnapshot]]:
    rows = load_snapshot_rows(session, model.tenant_id, now - LOOKBACK, now, R1_FEATURES, source)
    latest: dict[str, datetime] = {}
    for _, s in rows:
        latest[s.entity_id] = max(latest.get(s.entity_id, s.as_of), s.as_of)
    return [(i, s) for i, s in rows if s.as_of == latest[s.entity_id]]


def _threshold(evaluation: ModelEvaluation | None) -> float:
    promotion = (evaluation.criteria.get("promotion") or {}) if evaluation else {}
    value = promotion.get("alert_threshold")
    return float(value) if isinstance(value, int | float) else DEFAULT_THRESHOLD


def _decide(row: ScoredRow, present: float, active: bool, threshold: float) -> tuple[DecisionState, bool]:
    would = bool(row.calibrated and row.score is not None and row.score >= threshold)
    if row.raw_score is None or present < MIN_PRESENT_FRACTION:
        return DecisionState.INSUFFICIENT_DATA, False
    if not active:
        return DecisionState.SHADOW, would
    if not row.calibrated:
        return DecisionState.INSUFFICIENT_DATA, False
    return (DecisionState.SURFACED if would else DecisionState.BELOW_THRESHOLD), would


def _dec(value: float | None) -> Decimal | None:
    return None if value is None else round(Decimal(repr(value)), 6)


def _contributions(row: ScoredRow) -> list[dict[str, Any]]:
    return [
        clean_json(
            {
                "feature": c.feature,
                "value": c.value,
                "reference": c.reference,
                "direction": c.direction.value,
                "magnitude": c.magnitude,
                "reference_scope": c.reference_scope,
            }
        )
        for c in row.contributions
    ]


def _check(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise InferenceBudgetExceeded("per-tenant inference time budget exceeded")


def _link_case(
    session: Session, model: ModelVersion, pred_id: uuid.UUID, row: ScoredRow, as_of: datetime, now: datetime
) -> uuid.UUID | None:
    subject = uuid.UUID(row.entity_id)
    with scoped(session, DbScope.TENANT, model.tenant_id):
        eff = PolicyService(session).fraud_controls(model.tenant_id, at=now)
        machine = session.get(Machine, subject)
        linker = CaseLinker(session, model.tenant_id, now, eff.policy.case_grouping_window_hours)
        case = linker.link(
            CaseItem(
                source_type=CaseSourceType.PREDICTION,
                source_id=pred_id,
                code=PREDICTION_CODE,
                title=SURFACED_TITLE,
                severity=SignalSeverity.WARNING,
                observed_at=as_of,
                evidence={
                    "model": model.name,
                    "model_version": model.version,
                    "week_ending": as_of.isoformat(),
                    "compared_with": "this machine's own history",
                    "observations": list(row.explanations),
                    "note": "Statistical pattern only; it needs a person to review the facts.",
                },
                subject_type=SubjectType.MACHINE,
                subject_id=subject,
                policy_version=eff.version_stamp,
                machine_id=machine.id if machine is not None else None,
            )
        )
    return case.id if case is not None else None


def infer_model(
    session: Session,
    model_id: uuid.UUID,
    now: datetime,
    store: ObjectReader,
    run_id: uuid.UUID,
    deadline: float,
) -> InferenceResult:
    """Score one deployed model's latest machine-weeks (caller: SYSTEM scope, one transaction per model)."""
    started = time.monotonic()
    model = session.execute(select(ModelVersion).where(ModelVersion.id == model_id)).scalar_one_or_none()
    if model is None or model.status not in DEPLOYED_STATUSES:
        reason = f"Model is not deployed ({model.status.value if model else 'missing'}); nothing was scored."
        session.add(
            _audit(model.tenant_id if model else None, model_id, run_id, now, started, InferenceOutcome.SKIPPED, reason)
        )
        return InferenceResult(model_id, model.tenant_id if model else None, InferenceOutcome.SKIPPED, reason=reason)
    session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"infer:{model.id}"})
    active = model.status is ModelStatus.DEPLOYED_ACTIVE
    source = str(model.manifest.get("snapshot_source") or SOURCE_OBSERVED)
    rows = _latest_per_machine(session, model, now, source)
    if not rows:
        reason = f"No feature snapshots in the last {LOOKBACK.days // 7} weeks; nothing to score."
        session.add(_audit(model.tenant_id, model.id, run_id, now, started, InferenceOutcome.SKIPPED, reason))
        return InferenceResult(model.id, model.tenant_id, InferenceOutcome.SKIPPED, reason=reason)
    bundle = load_bundle(store, model)
    _check(deadline)
    matrix = build_matrix([s for _, s in rows], R1_FEATURES)
    base_rows, cand_rows = bundle.score(matrix)
    _check(deadline)
    ids: dict[tuple[str, datetime], list[uuid.UUID]] = {}
    cutoffs: dict[tuple[str, datetime], datetime] = {}
    for sid, s in rows:
        point = (s.entity_id, s.as_of)
        ids.setdefault(point, []).append(sid)
        if s.data_cutoff is not None:
            cutoffs[point] = max(cutoffs.get(point, s.data_cutoff), s.data_cutoff)
    done = set(
        session.execute(
            select(Prediction.subject_id, Prediction.as_of).where(Prediction.model_version_id == model.id)
        ).tuples()
    )
    evaluation = session.execute(
        select(ModelEvaluation).where(ModelEvaluation.model_version_id == model.id)
    ).scalar_one_or_none()
    approval_id = None
    if active:
        approval_id = session.execute(
            select(ModelApproval.id)
            .where(ModelApproval.model_version_id == model.id, ModelApproval.action == ModelAction.APPROVE)
            .order_by(ModelApproval.seq.desc())
            .limit(1)
        ).scalar_one_or_none()
    threshold = _threshold(evaluation)
    with scoped(session, DbScope.TENANT, model.tenant_id):
        policy_version = PolicyService(session).fraud_controls(model.tenant_id, at=now).version_stamp
    present = matrix.present_fraction()
    written = surfaced = 0
    for i, key in enumerate(matrix.keys):
        subject = uuid.UUID(key.entity_id)
        if (subject, key.as_of) in done:
            continue
        row, base = cand_rows[i], base_rows[i]
        state, would = _decide(row, float(present[i]), active, threshold)
        pred_id = uuid.uuid4()
        case_id = _link_case(session, model, pred_id, row, key.as_of, now) if state is DecisionState.SURFACED else None
        session.add(
            Prediction(
                id=pred_id,
                tenant_id=model.tenant_id,
                model_version_id=model.id,
                model_name=model.name,
                model_version_number=model.version,
                deployment_mode="ACTIVE" if active else "SHADOW",
                evaluation_id=evaluation.id if evaluation else None,
                approval_id=approval_id,
                subject_type=SubjectType.MACHINE.value,
                subject_id=subject,
                as_of=key.as_of,
                feature_set_hash=model.feature_set_hash,
                feature_snapshot_ids=ids.get((key.entity_id, key.as_of), []),
                data_cutoff=cutoffs.get((key.entity_id, key.as_of)),
                features_present=round(float(present[i]) * len(matrix.feature_codes)),
                score=_dec(row.score),
                raw_score=row.raw_score,
                calibrated=row.calibrated,
                baseline_score=_dec(base.score),
                baseline_raw_score=base.raw_score,
                threshold=_dec(threshold) or Decimal(0),
                would_surface=would,
                contributions=_contributions(row),
                explanations=list(row.explanations),
                policy_version=policy_version[:80],
                decision_state=state,
                case_id=case_id,
                inference_run_id=run_id,
                created_at=now,
            )
        )
        written += 1
        surfaced += state is DecisionState.SURFACED
    session.add(
        _audit(
            model.tenant_id, model.id, run_id, now, started, InferenceOutcome.OK, None, len(matrix), written, surfaced
        )
    )
    session.flush()
    return InferenceResult(model.id, model.tenant_id, InferenceOutcome.OK, len(matrix), written, surfaced)


def _reason(exc: BaseException) -> str:
    if isinstance(exc, InferenceBudgetExceeded):
        return "Per-tenant time budget exceeded; predictions for this run were discarded."
    if isinstance(exc, DependencyUnavailable | KeyError | ConnectionError):
        return f"Model artifact unavailable ({type(exc).__name__}); predictions are absent for this run."
    if isinstance(exc, ValueError) and "digest mismatch" in str(exc):
        return "Model artifact digest mismatch: the artifact was refused and not loaded."
    if isinstance(exc, DBAPIError):
        return f"Database error during inference ({type(exc.orig).__name__})."
    return f"{type(exc).__name__}: {str(exc)[:300]}"


def _run_one(
    sm: sessionmaker[Session],
    model_id: uuid.UUID,
    tenant_id: uuid.UUID,
    now: datetime,
    store: ObjectReader,
    run_id: uuid.UUID,
    budget_seconds: float,
) -> InferenceResult:
    started = time.monotonic()
    try:
        with sm.begin() as s:
            apply_scope(s, DbScope.SYSTEM, None, None)
            s.execute(text(f"SET LOCAL statement_timeout = '{int(budget_seconds * 1000)}ms'"))
            return infer_model(s, model_id, now, store, run_id, started + budget_seconds)
    except Exception as exc:  # never raise into the worker loop: record and move on
        reason = _reason(exc)
        log.warning("ml_inference_failed", model_version_id=str(model_id), tenant_id=str(tenant_id), reason=reason)
        try:
            with sm.begin() as s:
                apply_scope(s, DbScope.SYSTEM, None, None)
                s.add(_audit(tenant_id, model_id, run_id, now, started, InferenceOutcome.ERROR, reason))
        except Exception:
            log.exception("ml_inference_audit_failed", model_version_id=str(model_id))
        return InferenceResult(model_id, tenant_id, InferenceOutcome.ERROR, reason=reason)


def run_inference_cycle(
    sm: sessionmaker[Session],
    now: datetime,
    store: ObjectReader,
    *,
    tenant_ids: list[uuid.UUID] | None = None,
    budget_seconds: float = TENANT_BUDGET_SECONDS,
) -> InferenceCycleResult:
    """Score every deployed model (optionally only some tenants'). Never raises."""
    result = InferenceCycleResult(uuid.uuid4())
    try:
        with sm.begin() as s:
            apply_scope(s, DbScope.SYSTEM, None, None)
            if not inference_enabled(s):
                started = time.monotonic()
                s.add(_audit(None, None, result.run_id, now, started, InferenceOutcome.SKIPPED, SWITCH_OFF_REASON))
                result.switched_off = True
                return result
            stmt = select(ModelVersion.id, ModelVersion.tenant_id).where(ModelVersion.status.in_(DEPLOYED_STATUSES))
            if tenant_ids is not None:
                stmt = stmt.where(ModelVersion.tenant_id.in_(tenant_ids))
            targets = list(s.execute(stmt.order_by(ModelVersion.tenant_id, ModelVersion.name)).tuples())
    except Exception:
        log.exception("ml_inference_cycle_failed")
        return result
    for model_id, tenant_id in targets:
        result.results.append(_run_one(sm, model_id, tenant_id, now, store, result.run_id, budget_seconds))
    return result
