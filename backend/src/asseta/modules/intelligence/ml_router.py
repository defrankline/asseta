"""ML governance API. Platform console (`/api/v1/platform/ml/...`, platform.ml.read / platform.ml.manage): model
versions with evaluation vs baseline and the lifecycle log, lifecycle actions, the inference hard switch, per-tenant
readiness, and synchronous (bounded) snapshot/training triggers. Tenant (`/api/v1/tenant/ml/status`): readiness and
deployment facts in plain terms — never a score.

Triggers run inside the request transaction: facts and snapshots are read/written in the tenant's own RLS scope,
governance rows in the platform scope. Bounds: <= 26 week ends per snapshot call, <= 52 weeks of snapshots per
training run (the CLI `asseta-ml` runs the same code for cron/backfills)."""

import uuid
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, time, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.clock import get_now
from asseta.core.config import get_settings
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation, NotFound
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.models import AppUser
from asseta.modules.identity.principal import RequestContext
from asseta.modules.intelligence.feature_store import snapshot_tenant, sync_feature_definitions
from asseta.modules.intelligence.ml_dto import (
    MlApprovalDto,
    MlDriftDto,
    MlEvaluationDto,
    MlManifestSummaryDto,
    MlModelActionIn,
    MlModelVersionDetailDto,
    MlModelVersionDto,
    MlMonitoringDto,
    MlReadinessDto,
    MlSettingsDto,
    MlSettingsIn,
    MlSnapshotRunDto,
    MlSnapshotRunIn,
    MlTrainingRunDto,
    TenantMlDeploymentDto,
    TenantMlState,
    TenantMlStatusDto,
    TenantPredictionDto,
)
from asseta.modules.intelligence.ml_lifecycle import MlGovernanceService, current_ml_setting
from asseta.modules.intelligence.ml_models import (
    ANOMALY_MODEL_NAME,
    DEPLOYED_STATUSES,
    ModelAction,
    ModelApproval,
    ModelEvaluation,
    ModelReadiness,
    ModelStatus,
    ModelVersion,
    ReadinessState,
)
from asseta.modules.intelligence.ml_monitoring import monitoring_stats
from asseta.modules.intelligence.ml_monitoring_models import DecisionState, ModelDrift, Prediction
from asseta.modules.intelligence.ml_training import tracker_from_settings, train_tenant
from asseta.modules.intelligence.router import CASE_READ, SIGNAL_READ
from asseta.modules.tenancy.models import Tenant

ML_READ = requires("platform.ml.read", S.PLATFORM, "View ML model versions, evaluations, readiness and settings")
ML_MANAGE = requires("platform.ml.manage", S.PLATFORM, "Approve, deploy, roll back and disable ML models; run training")
CATALOG.register_menu(
    MenuDef(
        "platform.models", S.PLATFORM, "Models", "/platform/models", 80, "platform.ml.read", "platform.intelligence"
    )
)

platform_router = APIRouter(prefix="/api/v1/platform/ml", tags=["ml-governance"], responses=ERROR_RESPONSES)
tenant_router = APIRouter(prefix="/api/v1/tenant/ml", tags=["ml-governance"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
IdemKey = Annotated[str | None, Header()]
Read = Annotated[RequestContext, Depends(ML_READ)]
Manage = Annotated[RequestContext, Depends(ML_MANAGE)]


def _tenant_names(session: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = session.execute(select(Tenant.id, Tenant.display_name).where(Tenant.id.in_(ids))).tuples().all()
    return dict(rows)


def model_dtos(session: Session, models: list[ModelVersion]) -> list[MlModelVersionDto]:
    ids = [m.id for m in models]
    passed = dict(
        session.execute(
            select(ModelEvaluation.model_version_id, ModelEvaluation.passed).where(
                ModelEvaluation.model_version_id.in_(ids)
            )
        )
        .tuples()
        .all()
    )
    names = _tenant_names(session, {m.tenant_id for m in models})
    return [
        MlModelVersionDto.model_validate(m).model_copy(
            update={"tenant_name": names.get(m.tenant_id), "evaluation_passed": passed.get(m.id)}
        )
        for m in models
    ]


def readiness_dtos(session: Session, rows: list[ModelReadiness]) -> list[MlReadinessDto]:
    names = _tenant_names(session, {r.tenant_id for r in rows})
    return [MlReadinessDto.model_validate(r).model_copy(update={"tenant_name": names.get(r.tenant_id)}) for r in rows]


def _manifest_summary(manifest: dict[str, Any]) -> MlManifestSummaryDto:
    splits = manifest.get("splits") or {}
    return MlManifestSummaryDto(
        rows={k: int(v.get("rows", 0)) for k, v in splits.items()},
        entities=max((int(v.get("entities", 0)) for v in splits.values()), default=0),
        feature_codes=list(manifest.get("feature_codes") or []),
        train_end=manifest.get("train_end"),
        validation_end=manifest.get("validation_end"),
        purged_rows=manifest.get("purged_rows"),
        content_hash=manifest.get("content_hash"),
    )


def _detail(session: Session, svc: MlGovernanceService, model_id: uuid.UUID) -> MlModelVersionDetailDto:
    model = svc.model(model_id)
    evaluation = svc.evaluation(model.id)
    approvals = list(
        session.execute(
            select(ModelApproval).where(ModelApproval.model_version_id == model.id).order_by(ModelApproval.seq)
        ).scalars()
    )
    drift = session.execute(
        select(ModelDrift)
        .where(ModelDrift.model_version_id == model.id)
        .order_by(ModelDrift.computed_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    deciders = {a.decided_by for a in approvals if a.decided_by}
    names = (
        dict(session.execute(select(AppUser.id, AppUser.display_name).where(AppUser.id.in_(deciders))).tuples().all())
        if deciders
        else {}
    )
    return MlModelVersionDetailDto(
        model=model_dtos(session, [model])[0],
        evaluation=MlEvaluationDto.model_validate(evaluation) if evaluation else None,
        approvals=[
            MlApprovalDto.model_validate(a).model_copy(
                update={"decided_by_name": names.get(a.decided_by) if a.decided_by else None}
            )
            for a in approvals
        ],
        manifest=_manifest_summary(model.manifest),
        drift=MlDriftDto.model_validate(drift) if drift else None,
        monitoring=MlMonitoringDto(**asdict(monitoring_stats(session, model.id))),
    )


@platform_router.get("/models", response_model=Page[MlModelVersionDto], operation_id="listMlModelVersions")
def list_models(
    session: DbSession,
    _: Read,
    paging: Annotated[PageParams, Depends(page_params)],
    tenant_id: uuid.UUID | None = None,
    status: ModelStatus | None = None,
    name: str | None = None,
) -> Page[MlModelVersionDto]:
    stmt = select(ModelVersion).order_by(ModelVersion.created_at.desc(), ModelVersion.version.desc())
    if tenant_id is not None:
        stmt = stmt.where(ModelVersion.tenant_id == tenant_id)
    if status is not None:
        stmt = stmt.where(ModelVersion.status == status)
    if name:
        stmt = stmt.where(ModelVersion.name == name)
    rows, total = paginate(session, stmt, paging)
    return Page(items=model_dtos(session, rows), total=total, page=paging.page, page_size=paging.page_size)


@platform_router.get("/models/{model_id}", response_model=MlModelVersionDetailDto, operation_id="getMlModelVersion")
def get_model(model_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> MlModelVersionDetailDto:
    return _detail(session, MlGovernanceService(session, ctx.audit_actor(), now), model_id)


def _action_route(action: ModelAction, path: str, op: str) -> None:
    def handler(
        model_id: uuid.UUID,
        body: MlModelActionIn,
        session: DbSession,
        now: Now,
        ctx: Manage,
        idempotency_key: IdemKey = None,
    ) -> MlModelVersionDetailDto:
        guard = IdempotencyGuard(session, "platform", f"{op}:{model_id}", idempotency_key, request_hash(body))
        if (replay := guard.begin()) is not None:
            return MlModelVersionDetailDto.model_validate(replay)
        svc = MlGovernanceService(session, ctx.audit_actor(), now)
        svc.act(model_id, action, body.reason, body.lock_version)
        dto = _detail(session, svc, model_id)
        guard.complete(dto)
        return dto

    handler.__name__ = op
    platform_router.post(f"/models/{{model_id}}/{path}", response_model=MlModelVersionDetailDto, operation_id=op)(
        handler
    )


for _action, _path, _op in (
    (ModelAction.APPROVE, "approve", "approveMlModelVersion"),
    (ModelAction.REJECT, "reject", "rejectMlModelVersion"),
    (ModelAction.DEPLOY_SHADOW, "deploy-shadow", "deployMlModelVersionShadow"),
    (ModelAction.DEPLOY_ACTIVE, "deploy-active", "deployMlModelVersionActive"),
    (ModelAction.ROLLBACK, "rollback", "rollbackMlModelVersion"),
    (ModelAction.DISABLE, "disable", "disableMlModelVersion"),
    (ModelAction.RETIRE, "retire", "retireMlModelVersion"),
):
    _action_route(_action, _path, _op)


def _settings_dto(session: Session) -> MlSettingsDto:
    s = current_ml_setting(session)
    return MlSettingsDto(
        inference_enabled=s.inference_enabled,
        reason=s.reason,
        updated_by=s.updated_by,
        updated_at=s.updated_at,
        lock_version=s.lock_version,
    )


@platform_router.get("/settings", response_model=MlSettingsDto, operation_id="getMlSettings")
def get_ml_settings(session: DbSession, _: Read) -> MlSettingsDto:
    return _settings_dto(session)


@platform_router.put("/settings", response_model=MlSettingsDto, operation_id="updateMlSettings")
def update_ml_settings(body: MlSettingsIn, session: DbSession, now: Now, ctx: Manage) -> MlSettingsDto:
    expected = None if body.lock_version in (None, 0) else body.lock_version
    MlGovernanceService(session, ctx.audit_actor(), now).update_settings(body.inference_enabled, body.reason, expected)
    return _settings_dto(session)


@platform_router.get("/readiness", response_model=Page[MlReadinessDto], operation_id="listMlReadiness")
def list_readiness(
    session: DbSession,
    _: Read,
    paging: Annotated[PageParams, Depends(page_params)],
    status: ReadinessState | None = None,
    tenant_id: uuid.UUID | None = None,
) -> Page[MlReadinessDto]:
    """Latest readiness per (tenant, model name)."""
    latest = (
        select(ModelReadiness.id)
        .distinct(ModelReadiness.tenant_id, ModelReadiness.model_name)
        .order_by(ModelReadiness.tenant_id, ModelReadiness.model_name, ModelReadiness.computed_at.desc())
    )
    stmt = select(ModelReadiness).where(ModelReadiness.id.in_(latest)).order_by(ModelReadiness.computed_at.desc())
    if status is not None:
        stmt = stmt.where(ModelReadiness.status == status)
    if tenant_id is not None:
        stmt = stmt.where(ModelReadiness.tenant_id == tenant_id)
    rows, total = paginate(session, stmt, paging)
    return Page(items=readiness_dtos(session, rows), total=total, page=paging.page, page_size=paging.page_size)


def _idempotent[T: BaseModel](
    session: Session, route: str, key: str | None, body: Any, model: type[T], work: Callable[[], T]
) -> T:
    guard = IdempotencyGuard(session, "platform", route, key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return model.model_validate(replay)
    dto = work()
    guard.complete(dto)
    return dto


@platform_router.post("/tenants/{tenant_id}/snapshots", response_model=MlSnapshotRunDto, operation_id="runMlSnapshots")
def run_snapshots(
    tenant_id: uuid.UUID,
    body: MlSnapshotRunIn,
    session: DbSession,
    now: Now,
    ctx: Manage,
    idempotency_key: IdemKey = None,
) -> MlSnapshotRunDto:
    if body.to_date < body.from_date:
        raise BusinessRuleViolation("to_date is before from_date", code="INVALID_RANGE")

    def work() -> MlSnapshotRunDto:
        sync_feature_definitions(session)
        start = datetime.combine(body.from_date, time.min, UTC) - timedelta(days=1)  # tz slack; week ends filter
        end = datetime.combine(body.to_date, time.min, UTC) + timedelta(days=2)
        result = snapshot_tenant(session, tenant_id, start, end, now)
        dto = MlSnapshotRunDto(
            run_id=result.run_id,
            tenant_id=tenant_id,
            week_ends=result.week_ends,
            machines=result.machines,
            written=result.written,
            skipped_existing=result.skipped_existing,
            skipped_future=result.skipped_future,
        )
        AuditService(session).record(
            actor=ctx.audit_actor(),
            action="platform.ml.snapshot.completed",
            entity_type="feature_snapshot",
            entity_id=result.run_id,
            tenant_id=tenant_id,
            after=dto.model_dump(mode="json", exclude={"week_ends"}),
        )
        return dto

    return _idempotent(session, f"runMlSnapshots:{tenant_id}", idempotency_key, body, MlSnapshotRunDto, work)


@platform_router.post("/tenants/{tenant_id}/train", response_model=MlTrainingRunDto, operation_id="runMlTraining")
def run_training(
    tenant_id: uuid.UUID,
    request: Request,
    session: DbSession,
    now: Now,
    ctx: Manage,
    idempotency_key: IdemKey = None,
) -> MlTrainingRunDto:
    def work() -> MlTrainingRunDto:
        if session.get(Tenant, tenant_id) is None:
            raise NotFound("Tenant not found")
        sync_feature_definitions(session)
        tracker = getattr(request.app.state, "ml_tracker", None) or tracker_from_settings(get_settings())
        result = train_tenant(session, tenant_id, now, request.app.state.object_store, tracker, ctx.audit_actor())
        return MlTrainingRunDto(
            readiness=readiness_dtos(session, [result.readiness])[0],
            model=model_dtos(session, [result.model])[0] if result.model else None,
        )

    return _idempotent(session, f"runMlTraining:{tenant_id}", idempotency_key, {}, MlTrainingRunDto, work)


# --- tenant ----------------------------------------------------------------------------------------------------------
@tenant_router.get("/status", response_model=TenantMlStatusDto, operation_id="getTenantMlStatus")
def tenant_status(session: DbSession, ctx: Annotated[RequestContext, Depends(SIGNAL_READ)]) -> TenantMlStatusDto:
    name = ANOMALY_MODEL_NAME
    readiness = session.execute(
        select(ModelReadiness)
        .where(ModelReadiness.tenant_id == ctx.tenant_id, ModelReadiness.model_name == name)
        .order_by(ModelReadiness.computed_at.desc(), ModelReadiness.id)
        .limit(1)
    ).scalar_one_or_none()
    deployed = session.execute(
        select(ModelVersion).where(
            ModelVersion.tenant_id == ctx.tenant_id,
            ModelVersion.name == name,
            ModelVersion.status.in_(DEPLOYED_STATUSES),
        )
    ).scalar_one_or_none()
    enabled = current_ml_setting(session).inference_enabled
    deployment = (
        TenantMlDeploymentDto(
            name=deployed.name,
            version=deployed.version,
            mode="ACTIVE" if deployed.status is ModelStatus.DEPLOYED_ACTIVE else "SHADOW",
            deployed_at=deployed.deployed_at,
        )
        if deployed
        else None
    )
    state, label, summary = _plain_state(enabled, readiness, deployment)
    return TenantMlStatusDto(
        model_name=name,
        state=state,
        label=label,
        readiness=readiness_dtos(session, [readiness])[0] if readiness else None,
        deployed=deployment,
        inference_enabled=enabled,
        summary=summary,
    )


def _plain_state(
    enabled: bool, readiness: ModelReadiness | None, deployment: TenantMlDeploymentDto | None
) -> tuple[TenantMlState, str, str]:
    """(state, short label, one-sentence summary) — plain language, never a score."""
    if not enabled:
        off = "Anomaly models are switched off platform-wide; deterministic checks keep working."
        return "MODEL_OFF", "Model off", off
    if deployment is not None and deployment.mode == "ACTIVE":
        return "ACTIVE", "Active", "An approved model is active alongside the deterministic checks."
    if deployment is not None:
        shadow = "A model runs in shadow mode: it is observed by the platform and never shown as findings."
        return "LEARNING_SHADOW", "Learning (shadow)", shadow
    if readiness is None:
        return (
            "NOT_ASSESSED",
            "Not assessed yet",
            "Not assessed yet: anomaly scoring starts once machines accumulate observed weeks.",
        )
    if readiness.status is ReadinessState.INSUFFICIENT_DATA:
        text = "Not enough history yet: " + " ".join(readiness.reasons)
        return "NOT_ENOUGH_HISTORY", text, text
    return (
        "EVALUATING",
        "Being evaluated",
        "Enough history; a model is being evaluated. Deterministic checks keep working meanwhile.",
    )


@tenant_router.get("/predictions", response_model=Page[TenantPredictionDto], operation_id="listTenantPredictions")
def tenant_predictions(
    session: DbSession,
    _: Annotated[RequestContext, Depends(CASE_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    machine_id: uuid.UUID | None = None,
) -> Page[TenantPredictionDto]:
    """Surfaced model observations only (RLS also hides every other state from tenants); no scores."""
    stmt = (
        select(Prediction)
        .where(Prediction.decision_state == DecisionState.SURFACED)
        .order_by(Prediction.as_of.desc(), Prediction.id)
    )
    if machine_id is not None:
        stmt = stmt.where(Prediction.subject_id == machine_id)
    rows, total = paginate(session, stmt, paging)
    items = [
        TenantPredictionDto(
            id=p.id,
            machine_id=p.subject_id,
            week_ending=p.as_of,
            model_name=p.model_name,
            model_version=p.model_version_number,
            observations=list(p.explanations),
            case_id=p.case_id,
            created_at=p.created_at,
        )
        for p in rows
    ]
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)
