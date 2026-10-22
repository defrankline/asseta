"""Risk signals and investigation cases (tenant scope only). Wording is neutral: signals "need review", reviewers
record CONFIRMED_ISSUE / UNCONFIRMED / LEGITIMATE_EXPLANATION — no endpoint or field asserts misconduct."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.core.search import ilike_any
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.intelligence.cases import CaseService, case_dtos
from asseta.modules.intelligence.dto import (
    AnomalyCaseDetailDto,
    AnomalyCaseDto,
    CaseAssignIn,
    CaseNoteDto,
    CaseNoteIn,
    CaseReopenIn,
    CaseResolveIn,
    RiskSignalDto,
)
from asseta.modules.intelligence.models import (
    AnomalyCase,
    CaseStatus,
    RiskSignal,
    RuleCode,
    SignalSeverity,
    SignalStatus,
    SubjectType,
)

SIGNAL_READ = requires("tenant.signal.read", S.TENANT, "View deterministic risk signals and their evidence")
CASE_READ = requires("tenant.case.read", S.TENANT, "View investigation cases, linked evidence, notes and outcomes")
CASE_MANAGE = requires("tenant.case.manage", S.TENANT, "Assign, annotate and reopen investigation cases")
CASE_RESOLVE = requires("tenant.case.resolve", S.TENANT, "Resolve investigation cases with a recorded outcome")
CATALOG.register_menu(
    MenuDef("tenant.cases", S.TENANT, "Investigations", "/tenant/cases", 63, "tenant.case.read", "tenant.risk")
)

router = APIRouter(prefix="/api/v1/tenant", tags=["intelligence"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
IdemKey = Annotated[str | None, Header()]


@router.get("/risk-signals", response_model=Page[RiskSignalDto], operation_id="listRiskSignals")
def list_signals(
    session: DbSession,
    _: Annotated[RequestContext, Depends(SIGNAL_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    rule_code: RuleCode | None = None,
    severity: SignalSeverity | None = None,
    status: SignalStatus | None = None,
    subject_type: SubjectType | None = None,
    subject_id: uuid.UUID | None = None,
    machine_id: uuid.UUID | None = None,
    observed_from: datetime | None = None,
    observed_to: datetime | None = None,
) -> Page[RiskSignalDto]:
    stmt = select(RiskSignal).order_by(RiskSignal.created_at.desc(), RiskSignal.id)
    filters = {
        RiskSignal.rule_code: rule_code,
        RiskSignal.severity: severity,
        RiskSignal.status: status,
        RiskSignal.subject_type: subject_type,
        RiskSignal.subject_id: subject_id,
        RiskSignal.machine_id: machine_id,
    }
    for col, value in filters.items():
        if value is not None:
            stmt = stmt.where(col == value)
    if observed_from is not None:
        stmt = stmt.where(RiskSignal.window_end >= observed_from)
    if observed_to is not None:
        stmt = stmt.where(RiskSignal.window_start <= observed_to)
    if (match := ilike_any(paging.q, RiskSignal.rule_code, RiskSignal.dedupe_key)) is not None:
        stmt = stmt.where(match)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[RiskSignalDto.model_validate(r) for r in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/cases", response_model=Page[AnomalyCaseDto], operation_id="listAnomalyCases")
def list_cases(
    session: DbSession,
    _: Annotated[RequestContext, Depends(CASE_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    status: CaseStatus | None = None,
    severity: SignalSeverity | None = None,
    assignee_user_id: uuid.UUID | None = None,
    subject_type: SubjectType | None = None,
    subject_id: uuid.UUID | None = None,
    machine_id: uuid.UUID | None = None,
) -> Page[AnomalyCaseDto]:
    stmt = select(AnomalyCase).order_by(AnomalyCase.last_signal_at.desc(), AnomalyCase.id)
    filters = {
        AnomalyCase.status: status,
        AnomalyCase.severity: severity,
        AnomalyCase.assignee_user_id: assignee_user_id,
        AnomalyCase.subject_type: subject_type,
        AnomalyCase.subject_id: subject_id,
        AnomalyCase.machine_id: machine_id,
    }
    for col, value in filters.items():
        if value is not None:
            stmt = stmt.where(col == value)
    if (match := ilike_any(paging.q, AnomalyCase.case_number, AnomalyCase.title)) is not None:
        stmt = stmt.where(match)
    rows, total = paginate(session, stmt, paging)
    return Page(items=case_dtos(session, rows), total=total, page=paging.page, page_size=paging.page_size)


@router.get("/cases/{case_id}", response_model=AnomalyCaseDetailDto, operation_id="getAnomalyCase")
def get_case(
    case_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(CASE_READ)]
) -> AnomalyCaseDetailDto:
    return CaseService(session, ctx, now).detail(case_id)


def _guard(session: Session, ctx: RequestContext, route: str, key: str | None, body: BaseModel) -> IdempotencyGuard:
    return IdempotencyGuard(session, str(ctx.tenant_id), route, key, request_hash(body))


@router.post("/cases/{case_id}/assign", response_model=AnomalyCaseDetailDto, operation_id="assignAnomalyCase")
def assign_case(
    case_id: uuid.UUID,
    body: CaseAssignIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CASE_MANAGE)],
    idempotency_key: IdemKey = None,
) -> AnomalyCaseDetailDto:
    guard = _guard(session, ctx, f"assignAnomalyCase:{case_id}", idempotency_key, body)
    if (replay := guard.begin()) is not None:
        return AnomalyCaseDetailDto.model_validate(replay)
    dto = CaseService(session, ctx, now).assign(case_id, body)
    guard.complete(dto)
    return dto


@router.post("/cases/{case_id}/notes", response_model=CaseNoteDto, status_code=201, operation_id="addAnomalyCaseNote")
def add_note(
    case_id: uuid.UUID,
    body: CaseNoteIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CASE_MANAGE)],
    idempotency_key: IdemKey = None,
) -> CaseNoteDto:
    guard = _guard(session, ctx, f"addAnomalyCaseNote:{case_id}", idempotency_key, body)
    if (replay := guard.begin()) is not None:
        return CaseNoteDto.model_validate(replay)
    dto = CaseService(session, ctx, now).add_note(case_id, body)
    guard.complete(dto, 201)
    return dto


@router.post("/cases/{case_id}/resolve", response_model=AnomalyCaseDetailDto, operation_id="resolveAnomalyCase")
def resolve_case(
    case_id: uuid.UUID,
    body: CaseResolveIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CASE_RESOLVE)],
    idempotency_key: IdemKey = None,
) -> AnomalyCaseDetailDto:
    guard = _guard(session, ctx, f"resolveAnomalyCase:{case_id}", idempotency_key, body)
    if (replay := guard.begin()) is not None:
        return AnomalyCaseDetailDto.model_validate(replay)
    dto = CaseService(session, ctx, now).resolve(case_id, body)
    guard.complete(dto)
    return dto


@router.post("/cases/{case_id}/reopen", response_model=AnomalyCaseDetailDto, operation_id="reopenAnomalyCase")
def reopen_case(
    case_id: uuid.UUID,
    body: CaseReopenIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CASE_MANAGE)],
    idempotency_key: IdemKey = None,
) -> AnomalyCaseDetailDto:
    guard = _guard(session, ctx, f"reopenAnomalyCase:{case_id}", idempotency_key, body)
    if (replay := guard.begin()) is not None:
        return AnomalyCaseDetailDto.model_validate(replay)
    dto = CaseService(session, ctx, now).reopen(case_id, body)
    guard.complete(dto)
    return dto
