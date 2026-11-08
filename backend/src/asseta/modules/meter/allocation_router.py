"""Work allocation ledger and daily operational report endpoints (DEC-032 A1, A4). Every endpoint needs the tenant's
ENGINE_HOURS capability. Field users are scoped to the machines assigned to them; the same corrections and reviews
go through the permission checks whatever the role name."""

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.accountability.names import named
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import gated
from asseta.modules.identity.principal import RequestContext
from asseta.modules.meter.allocation_dto import (
    AllocationCorrectionDto,
    AllocationCorrectionIn,
    AllocationDayDto,
    DailyReportDto,
    DailyReportIn,
    DailyReportPrefillDto,
    DailyReportReviewIn,
    WorkAllocationDto,
)
from asseta.modules.meter.allocation_models import AllocationKind, AllocationStatus, DailyReportStatus
from asseta.modules.meter.allocation_service import WorkAllocationService
from asseta.modules.meter.daily_report import DailyReportService
from asseta.modules.meter.engine_dto import MeterDecisionIn
from asseta.modules.meter.router import APPROVE as _APPROVE
from asseta.modules.meter.router import CAPTURE as _CAPTURE
from asseta.modules.meter.router import METER_READ as _METER_READ
from asseta.modules.meter.router import REVIEW as _REVIEW
from asseta.modules.policy.capabilities import ENGINE_HOURS

METER_READ = gated(_METER_READ, ENGINE_HOURS)
CAPTURE = gated(_CAPTURE, ENGINE_HOURS)
REVIEW = gated(_REVIEW, ENGINE_HOURS)
APPROVE = gated(_APPROVE, ENGINE_HOURS)

for _menu in (
    MenuDef(
        "tenant.work_allocations",
        S.TENANT,
        "Work allocations",
        "/tenant/work-allocations",
        50,
        "tenant.meter.read",
        group="tenant.engine_hours",
    ),
    MenuDef(
        "tenant.daily_reports",
        S.TENANT,
        "Daily reports",
        "/tenant/daily-reports",
        51,
        "tenant.meter.read",
        group="tenant.engine_hours",
    ),
):
    CATALOG.register_menu(_menu)

router = APIRouter(prefix="/api/v1/tenant", tags=["engine-hours"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
Paging = Annotated[PageParams, Depends(page_params)]


# --- work allocations -------------------------------------------------------------------------------------------
@router.get("/work-allocations", response_model=Page[WorkAllocationDto], operation_id="listWorkAllocations")
@named
def list_allocations(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(METER_READ)],
    paging: Paging,
    machine_id: uuid.UUID | None = None,
    day_from: Annotated[date | None, Query(alias="from")] = None,
    day_to: Annotated[date | None, Query(alias="to")] = None,
    customer_id: uuid.UUID | None = None,
    kind: AllocationKind | None = None,
    status: Annotated[AllocationStatus | None, Query(description="Default: ACTIVE")] = None,
    job_id: uuid.UUID | None = None,
) -> Page[WorkAllocationDto]:
    """The work allocation ledger, latest work date first (`q`: machine code or name)."""
    svc = WorkAllocationService(session, ctx, now)
    rows, total = paginate(
        session, svc.query(paging.q, machine_id, day_from, day_to, customer_id, kind, status, job_id), paging
    )
    return Page(items=svc.dtos(rows), total=total, page=paging.page, page_size=paging.page_size)


@router.get(
    "/work-allocations/reconciliation",
    response_model=list[AllocationDayDto],
    operation_id="listWorkAllocationReconciliation",
)
@named
def reconciliation(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(METER_READ)],
    day_from: Annotated[date, Query(alias="from")],
    day_to: Annotated[date, Query(alias="to")],
    machine_id: uuid.UUID | None = None,
) -> list[AllocationDayDto]:
    """Per machine and day: total engine hours = customer + authorized + unexplained, the difference displayed."""
    return WorkAllocationService(session, ctx, now).reconciliation(machine_id, day_from, day_to)


@router.get(
    "/work-allocations/corrections/{group_id}",
    response_model=AllocationCorrectionDto,
    operation_id="getWorkAllocationCorrection",
)
@named
def get_correction(
    group_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(METER_READ)]
) -> AllocationCorrectionDto:
    return WorkAllocationService(session, ctx, now).correction(group_id)


@router.get("/work-allocations/{allocation_id}", response_model=WorkAllocationDto, operation_id="getWorkAllocation")
@named
def get_allocation(
    allocation_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(METER_READ)]
) -> WorkAllocationDto:
    svc = WorkAllocationService(session, ctx, now)
    return svc.dtos([svc.row(allocation_id)])[0]


@router.post(
    "/work-allocations/{allocation_id}/corrections",
    response_model=AllocationCorrectionDto,
    status_code=201,
    operation_id="proposeWorkAllocationCorrection",
)
@named
def propose_correction(
    allocation_id: uuid.UUID,
    body: AllocationCorrectionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REVIEW)],
) -> AllocationCorrectionDto:
    """Propose new entries replacing this one (one or more parts adding up to its hours; reason required)."""
    return WorkAllocationService(session, ctx, now).propose_correction(allocation_id, body)


@router.post(
    "/work-allocations/corrections/{group_id}/decision",
    response_model=AllocationCorrectionDto,
    operation_id="decideWorkAllocationCorrection",
)
@named
def decide_correction(
    group_id: uuid.UUID,
    body: MeterDecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(APPROVE)],
) -> AllocationCorrectionDto:
    return WorkAllocationService(session, ctx, now).decide_correction(group_id, body)


# --- daily operational reports -----------------------------------------------------------------------------------
@router.get("/daily-reports", response_model=Page[DailyReportDto], operation_id="listDailyReports")
@named
def list_daily_reports(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(METER_READ)],
    paging: Paging,
    machine_id: uuid.UUID | None = None,
    day_from: Annotated[date | None, Query(alias="from")] = None,
    day_to: Annotated[date | None, Query(alias="to")] = None,
    status: DailyReportStatus | None = None,
) -> Page[DailyReportDto]:
    svc = DailyReportService(session, ctx, now)
    rows, total = paginate(session, svc.query(paging.q, machine_id, day_from, day_to, status), paging)
    return Page(items=svc.dtos(rows), total=total, page=paging.page, page_size=paging.page_size)


@router.get("/daily-reports/prefill", response_model=DailyReportPrefillDto, operation_id="prefillDailyReport")
@named
def prefill(
    machine_id: uuid.UUID,
    report_date: date,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(METER_READ)],
) -> DailyReportPrefillDto:
    """The day's readings and allocations, to pre-fill the report form."""
    return DailyReportService(session, ctx, now).prefill(machine_id, report_date)


@router.get("/daily-reports/{report_id}", response_model=DailyReportDto, operation_id="getDailyReport")
@named
def get_daily_report(
    report_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(METER_READ)]
) -> DailyReportDto:
    svc = DailyReportService(session, ctx, now)
    return svc.dtos([svc.row(report_id)])[0]


@router.post("/daily-reports", response_model=DailyReportDto, status_code=201, operation_id="submitDailyReport")
@named
def submit_daily_report(
    body: DailyReportIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(CAPTURE)]
) -> DailyReportDto:
    return DailyReportService(session, ctx, now).submit(body, "API")


@router.post("/daily-reports/{report_id}/review", response_model=DailyReportDto, operation_id="reviewDailyReport")
@named
def review_daily_report(
    report_id: uuid.UUID,
    body: DailyReportReviewIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REVIEW)],
) -> DailyReportDto:
    """Mark reviewed, or return it to the submitter. Never by the person who submitted it."""
    return DailyReportService(session, ctx, now).review(report_id, body)
