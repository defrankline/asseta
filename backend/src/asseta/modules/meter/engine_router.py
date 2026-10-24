"""Engine-hour accountability endpoints (design B): meter baselines, the tenant's explanation lists, per-machine
reconciliation, the tenant-wide list of unallocated hours, classifications and reading corrections."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.lifecycle import IncludeInactive, LifecycleChangeIn
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.meter.engine_dto import (
    BaselineDto,
    BaselineFromReadingIn,
    BaselineIn,
    ClassificationDto,
    ClassificationIn,
    CorrectionDto,
    CorrectionIn,
    EngineHourReasonDto,
    EngineHourReasonIn,
    EngineHourReasonUpdateIn,
    MachineEngineHoursDto,
    MachineEngineHoursSummaryDto,
    MeterDecisionIn,
    ReconciliationStatus,
    UnallocatedSegmentDto,
)
from asseta.modules.meter.engine_models import EngineHourReasonKind, MeterProposalStatus
from asseta.modules.meter.engine_service import EngineHoursService
from asseta.modules.meter.ledger import SegmentClassification
from asseta.modules.meter.router import APPROVE, CAPTURE, METER_READ, REVIEW

CLASSIFY = requires(
    "tenant.meter.classify", S.TENANT, "Approve classifications of unallocated engine hours (second person)"
)
REASONS = requires("tenant.meter.reasons", S.TENANT, "Manage engine-hour activity categories and variance reasons")
# Engine hours group: reconcile, explain, decide, configure (server-scoped: field users see their machines only).
for _menu in (
    MenuDef(
        "tenant.engine_hours",
        S.TENANT,
        "Reconciliation",
        "/tenant/engine-hours",
        44,
        "tenant.meter.read",
        group="tenant.engine_hours",
    ),
    MenuDef(
        "tenant.engine_hours.unallocated",
        S.TENANT,
        "Hours to explain",
        "/tenant/engine-hours/unallocated",
        45,
        "tenant.meter.read",
        group="tenant.engine_hours",
    ),
    MenuDef(
        "tenant.engine_hours.classifications",
        S.TENANT,
        "Hour explanations",
        "/tenant/engine-hours/classifications",
        46,
        "tenant.meter.read",
        group="tenant.engine_hours",
    ),
    MenuDef(
        "tenant.meter_baselines",
        S.TENANT,
        "Meter baselines",
        "/tenant/meter-baselines",
        47,
        "tenant.meter.read",
        group="tenant.engine_hours",
    ),
    MenuDef(
        "tenant.meter_corrections",
        S.TENANT,
        "Reading corrections",
        "/tenant/meter-corrections",
        48,
        "tenant.meter.read",
        group="tenant.engine_hours",
    ),
    MenuDef(
        "tenant.engine_hour_reasons",
        S.TENANT,
        "Engine-hour reasons",
        "/tenant/engine-hour-reasons",
        49,
        "tenant.meter.reasons",
        group="tenant.engine_hours",
    ),
):
    CATALOG.register_menu(_menu)

router = APIRouter(prefix="/api/v1/tenant", tags=["engine-hours"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
Paging = Annotated[PageParams, Depends(page_params)]


def _slice[T](items: list[T], paging: PageParams) -> Page[T]:
    start = (paging.page - 1) * paging.page_size
    return Page(
        items=items[start : start + paging.page_size], total=len(items), page=paging.page, page_size=paging.page_size
    )


# --- baselines -------------------------------------------------------------------------------------------------
@router.get("/meter-baselines", response_model=Page[BaselineDto], operation_id="listMeterBaselines")
def list_baselines(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(METER_READ)],
    paging: Paging,
    machine_id: uuid.UUID | None = None,
    status: MeterProposalStatus | None = None,
) -> Page[BaselineDto]:
    """Baselines and proposals, newest first (`q`: machine code or name). Field users see their machines only."""
    svc = EngineHoursService(session, ctx, now)
    rows, total = paginate(session, svc.baseline_query(paging.q, machine_id, status), paging)
    return Page(items=svc.baseline_dtos(rows), total=total, page=paging.page, page_size=paging.page_size)


@router.get("/meter-baselines/{baseline_id}", response_model=BaselineDto, operation_id="getMeterBaseline")
def get_baseline(
    baseline_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(METER_READ)]
) -> BaselineDto:
    svc = EngineHoursService(session, ctx, now)
    return svc.baseline_dto(svc.baseline(baseline_id))


@router.post("/meter-baselines", response_model=BaselineDto, status_code=201, operation_id="proposeMeterBaseline")
def propose_baseline(
    body: BaselineIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(CAPTURE)]
) -> BaselineDto:
    """Propose a machine's initial engine-hour reading (with evidence). A second person approves it."""
    return EngineHoursService(session, ctx, now).propose_baseline(body)


@router.post(
    "/meter-baselines/from-reading",
    response_model=BaselineDto,
    status_code=201,
    operation_id="proposeMeterBaselineFromReading",
)
def propose_baseline_from_reading(
    body: BaselineFromReadingIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(REVIEW)]
) -> BaselineDto:
    """For machines with prior readings: propose an existing reading (default the earliest) as the baseline."""
    return EngineHoursService(session, ctx, now).propose_baseline_from_reading(body)


@router.post("/meter-baselines/{baseline_id}/decision", response_model=BaselineDto, operation_id="decideMeterBaseline")
def decide_baseline(
    baseline_id: uuid.UUID,
    body: MeterDecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(APPROVE)],
) -> BaselineDto:
    return EngineHoursService(session, ctx, now).decide_baseline(baseline_id, body)


# --- tenant lists ----------------------------------------------------------------------------------------------
@router.get("/engine-hour-reasons", response_model=Page[EngineHourReasonDto], operation_id="listEngineHourReasons")
def list_reasons(
    session: DbSession,
    _: Annotated[RequestContext, Depends(METER_READ)],
    paging: Paging,
    kind: EngineHourReasonKind | None = None,
    include_inactive: IncludeInactive = False,
) -> Page[EngineHourReasonDto]:
    """Non-customer activity categories and variance reasons (tenant data; `q`: code or name)."""
    rows, total = paginate(session, EngineHoursService.reason_query(paging.q, kind, include_inactive), paging)
    return Page(
        items=[EngineHourReasonDto.model_validate(r) for r in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get("/engine-hour-reasons/{reason_id}", response_model=EngineHourReasonDto, operation_id="getEngineHourReason")
def get_reason(
    reason_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(METER_READ)]
) -> EngineHourReasonDto:
    return EngineHourReasonDto.model_validate(EngineHoursService(session, ctx, now).reason(reason_id))


@router.post(
    "/engine-hour-reasons", response_model=EngineHourReasonDto, status_code=201, operation_id="createEngineHourReason"
)
def create_reason(
    body: EngineHourReasonIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(REASONS)]
) -> EngineHourReasonDto:
    return EngineHoursService(session, ctx, now).create_reason(body)


@router.put(
    "/engine-hour-reasons/{reason_id}", response_model=EngineHourReasonDto, operation_id="updateEngineHourReason"
)
def update_reason(
    reason_id: uuid.UUID,
    body: EngineHourReasonUpdateIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REASONS)],
) -> EngineHourReasonDto:
    return EngineHoursService(session, ctx, now).update_reason(reason_id, body)


@router.post(
    "/engine-hour-reasons/{reason_id}/deactivate",
    response_model=EngineHourReasonDto,
    operation_id="deactivateEngineHourReason",
)
def deactivate_reason(
    reason_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REASONS)],
) -> EngineHourReasonDto:
    """Refused for new classifications afterwards; past classifications keep the entry."""
    return EngineHoursService(session, ctx, now).set_reason_active(reason_id, False, body.reason, body.version)


@router.post(
    "/engine-hour-reasons/{reason_id}/reactivate",
    response_model=EngineHourReasonDto,
    operation_id="reactivateEngineHourReason",
)
def reactivate_reason(
    reason_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REASONS)],
) -> EngineHourReasonDto:
    return EngineHoursService(session, ctx, now).set_reason_active(reason_id, True, body.reason, body.version)


# --- reconciliation --------------------------------------------------------------------------------------------
@router.get(
    "/engine-hours/machines", response_model=Page[MachineEngineHoursSummaryDto], operation_id="listMachineEngineHours"
)
def list_machine_engine_hours(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(METER_READ)],
    paging: Paging,
    status: ReconciliationStatus | None = None,
) -> Page[MachineEngineHoursSummaryDto]:
    """Engine-hour reconciliation per machine (status, totals, open items; `q`: machine code or name)."""
    return _slice(EngineHoursService(session, ctx, now).summaries(paging.q, status), paging)


@router.get(
    "/engine-hours/machines/{machine_id}", response_model=MachineEngineHoursDto, operation_id="getMachineEngineHours"
)
def get_machine_engine_hours(
    machine_id: uuid.UUID,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(METER_READ)],
    at_from: Annotated[datetime | None, Query(alias="from")] = None,
    at_to: Annotated[datetime | None, Query(alias="to")] = None,
) -> MachineEngineHoursDto:
    """The machine's engine-hour ledger: intervals between consecutive readings, their segments (customer work or
    unallocated + classification) and totals. Derived from the readings on every call (never a stored balance)."""
    return EngineHoursService(session, ctx, now).reconciliation(machine_id, at_from, at_to)


@router.get(
    "/engine-hours/unallocated",
    response_model=Page[UnallocatedSegmentDto],
    operation_id="listUnallocatedEngineHours",
)
def list_unallocated(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(METER_READ)],
    paging: Paging,
    machine_id: uuid.UUID | None = None,
    classification: Annotated[
        SegmentClassification | None, Query(description="Default: open items (verified, unexplained)")
    ] = None,
    min_age_days: Annotated[int | None, Query(ge=0)] = None,
) -> Page[UnallocatedSegmentDto]:
    """Tenant-wide unallocated engine-hour segments, oldest first (`q`: machine code or name)."""
    svc = EngineHoursService(session, ctx, now)
    return _slice(svc.unallocated(paging.q, machine_id, classification, min_age_days), paging)


# --- classifications -------------------------------------------------------------------------------------------
@router.get(
    "/engine-hours/classifications",
    response_model=Page[ClassificationDto],
    operation_id="listEngineHourClassifications",
)
def list_classifications(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(METER_READ)],
    paging: Paging,
    machine_id: uuid.UUID | None = None,
    status: MeterProposalStatus | None = None,
) -> Page[ClassificationDto]:
    svc = EngineHoursService(session, ctx, now)
    rows, total = paginate(session, svc.classification_query(paging.q, machine_id, status), paging)
    return Page(items=svc.classification_dtos(rows), total=total, page=paging.page, page_size=paging.page_size)


@router.get(
    "/engine-hours/classifications/{classification_id}",
    response_model=ClassificationDto,
    operation_id="getEngineHourClassification",
)
def get_classification(
    classification_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(METER_READ)]
) -> ClassificationDto:
    svc = EngineHoursService(session, ctx, now)
    return svc.classification_dtos([svc.classification(classification_id)])[0]


@router.post(
    "/engine-hours/classifications",
    response_model=ClassificationDto,
    status_code=201,
    operation_id="proposeEngineHourClassification",
)
def propose_classification(
    body: ClassificationIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(REVIEW)]
) -> ClassificationDto:
    """Explain an unexplained segment (approved non-customer activity or identified variance). Takes effect when a
    second person with `tenant.meter.classify` approves (or directly, if the tenant policy needs no approval)."""
    return EngineHoursService(session, ctx, now).propose_classification(body)


@router.post(
    "/engine-hours/classifications/{classification_id}/decision",
    response_model=ClassificationDto,
    operation_id="decideEngineHourClassification",
)
def decide_classification(
    classification_id: uuid.UUID,
    body: MeterDecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CLASSIFY)],
) -> ClassificationDto:
    return EngineHoursService(session, ctx, now).decide_classification(classification_id, body)


# --- corrections -----------------------------------------------------------------------------------------------
@router.get("/meter-corrections", response_model=Page[CorrectionDto], operation_id="listMeterCorrections")
def list_corrections(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(METER_READ)],
    paging: Paging,
    machine_id: uuid.UUID | None = None,
    status: MeterProposalStatus | None = None,
) -> Page[CorrectionDto]:
    """Reading corrections, newest first (`q`: machine or reason). Field users see the ones they proposed."""
    svc = EngineHoursService(session, ctx, now)
    rows, total = paginate(session, svc.correction_query(paging.q, machine_id, status), paging)
    return Page(items=svc.correction_dtos(rows), total=total, page=paging.page, page_size=paging.page_size)


@router.get("/meter-corrections/{correction_id}", response_model=CorrectionDto, operation_id="getMeterCorrection")
def get_correction(
    correction_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(METER_READ)]
) -> CorrectionDto:
    svc = EngineHoursService(session, ctx, now)
    return svc.correction_dtos([svc.correction(correction_id)])[0]


@router.post("/meter-corrections", response_model=CorrectionDto, status_code=201, operation_id="proposeMeterCorrection")
def propose_correction(
    body: CorrectionIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(CAPTURE)]
) -> CorrectionDto:
    """Propose superseding a reading with a corrected one (reason >= 10 characters). Applied when a second person
    with `tenant.meter.approve` approves (or directly, if the tenant policy needs no second person)."""
    return EngineHoursService(session, ctx, now).propose_correction(body)


@router.post(
    "/meter-corrections/{correction_id}/decision", response_model=CorrectionDto, operation_id="decideMeterCorrection"
)
def decide_correction(
    correction_id: uuid.UUID,
    body: MeterDecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(APPROVE)],
) -> CorrectionDto:
    return EngineHoursService(session, ctx, now).decide_correction(correction_id, body)
