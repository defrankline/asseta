"""Revenue reconciliation endpoints (DEC-031 Phase 1): the daily machine sheet (R2), revenue differences and their
explanation / decision (R3), and the tenant's revenue reason list. Every endpoint needs the tenant's
REVENUE_RECONCILIATION capability (refused with REVENUE_RECONCILIATION_DISABLED while it is off)."""

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.lifecycle import IncludeInactive, LifecycleChangeIn
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.accountability.names import fill_names, named
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import gated, requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.policy.capabilities import REVENUE_RECONCILIATION
from asseta.modules.revenue.dto import (
    DailyMachineSheetDetailDto,
    DailyMachineSheetRowDto,
    NonRevenueActivityDto,
    NonRevenueApprovalDto,
    NonRevenueApprovalIn,
    NonRevenueDecisionIn,
    RevenueDecisionIn,
    RevenueDifferenceDto,
    RevenueExplanationIn,
    RevenueReasonDto,
    RevenueReasonIn,
    RevenueReasonUpdateIn,
)
from asseta.modules.revenue.models import NonRevenueApprovalStatus, RevenueDifferenceStatus
from asseta.modules.revenue.service import RevenueService

READ_PERMISSION = "tenant.revenue.read"
EXPLAIN_PERMISSION = "tenant.revenue.explain"
DECIDE_PERMISSION = "tenant.revenue.decide"
READ = gated(
    requires(READ_PERMISSION, S.TENANT, "View the daily machine sheet and revenue differences"),
    REVENUE_RECONCILIATION,
)
EXPLAIN = gated(
    requires(EXPLAIN_PERMISSION, S.TENANT, "Explain a revenue difference (a second person decides)"),
    REVENUE_RECONCILIATION,
)
DECIDE = gated(
    requires(DECIDE_PERMISSION, S.TENANT, "Decide on revenue differences and manage the revenue reason list"),
    REVENUE_RECONCILIATION,
)
for _menu in (
    MenuDef(
        "tenant.engine_hours.daily_sheet",
        S.TENANT,
        "Daily machine sheet",
        "/tenant/engine-hours/daily-sheet",
        43,
        READ_PERMISSION,
        group="tenant.engine_hours",
        capability=REVENUE_RECONCILIATION,
    ),
    MenuDef(
        "tenant.engine_hours.non_revenue",
        S.TENANT,
        "Non-revenue hours",
        "/tenant/non-revenue-approvals",
        42,
        READ_PERMISSION,
        group="tenant.engine_hours",
        capability=REVENUE_RECONCILIATION,
    ),
    MenuDef(
        "tenant.revenue_differences",
        S.TENANT,
        "Revenue differences",
        "/tenant/revenue-differences",
        68,
        READ_PERMISSION,
        group="tenant.finance",
        capability=REVENUE_RECONCILIATION,
    ),
    MenuDef(
        "tenant.revenue_reasons",
        S.TENANT,
        "Revenue reasons",
        "/tenant/revenue-reasons",
        69,
        DECIDE_PERMISSION,
        group="tenant.finance",
        capability=REVENUE_RECONCILIATION,
    ),
):
    CATALOG.register_menu(_menu)

router = APIRouter(prefix="/api/v1/tenant", tags=["revenue"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
Paging = Annotated[PageParams, Depends(page_params)]
DayFrom = Annotated[date | None, Query(description="First tenant-local day (default: 6 days before day_to)")]
DayTo = Annotated[date | None, Query(description="Last tenant-local day, inclusive (default: today)")]


# --- daily machine sheet (R2) -----------------------------------------------------------------------------------
@router.get("/daily-machine-sheet", response_model=Page[DailyMachineSheetRowDto], operation_id="listDailyMachineSheet")
@named
def list_daily_sheet(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(READ)],
    paging: Paging,
    machine_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    day_from: DayFrom = None,
    day_to: DayTo = None,
) -> Page[DailyMachineSheetRowDto]:
    """One row per machine per tenant-local day with activity (newest day first; `q`: machine code or name; at
    most 93 days). Derived from the engine-hour ledger, jobs, fuel, flags and money on every call."""
    rows = RevenueService(session, ctx, now).sheet_rows(paging.q, machine_id, site_id, day_from, day_to)
    start = (paging.page - 1) * paging.page_size
    return Page(
        items=rows[start : start + paging.page_size], total=len(rows), page=paging.page, page_size=paging.page_size
    )


@router.get(
    "/daily-machine-sheet/export.csv",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/csv": {}}}},
    operation_id="exportDailyMachineSheetCsv",
)
def export_daily_sheet(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(READ)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    machine_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    day_from: DayFrom = None,
    day_to: DayTo = None,
) -> StreamingResponse:
    """The list's rows (same filters, no paging) as CSV, one money column group per currency (audited export)."""
    svc = RevenueService(session, ctx, now)
    rows = fill_names(session, svc.sheet_rows(q, machine_id, site_id, day_from, day_to))
    body = svc.sheet_csv(rows)
    return StreamingResponse(
        iter([body]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="asseta-daily-machine-sheet.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.get(
    "/daily-machine-sheet/{machine_id}/{day}",
    response_model=DailyMachineSheetDetailDto,
    operation_id="getDailyMachineSheetDay",
)
@named
def get_daily_sheet_day(
    machine_id: uuid.UUID, day: date, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(READ)]
) -> DailyMachineSheetDetailDto:
    """One machine-day with the ids behind every figure: readings, ledger segments, jobs, money sources (invoice
    lines / prepaid consumption) and flag records."""
    return RevenueService(session, ctx, now).sheet_detail(machine_id, day)


# --- revenue differences (R3) -----------------------------------------------------------------------------------
@router.get("/revenue-differences", response_model=Page[RevenueDifferenceDto], operation_id="listRevenueDifferences")
@named
def list_differences(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(READ)],
    paging: Paging,
    status: RevenueDifferenceStatus | None = None,
    machine_id: uuid.UUID | None = None,
    day_from: DayFrom = None,
    day_to: DayTo = None,
) -> Page[RevenueDifferenceDto]:
    """Revenue differences to explain, newest period first (`q`: machine code/name or period key)."""
    svc = RevenueService(session, ctx, now)
    rows, total = paginate(session, svc.difference_query(paging.q, status, machine_id, day_from, day_to), paging)
    return Page(items=svc.difference_dtos(rows), total=total, page=paging.page, page_size=paging.page_size)


@router.get(
    "/revenue-differences/{difference_id}", response_model=RevenueDifferenceDto, operation_id="getRevenueDifference"
)
@named
def get_difference(
    difference_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(READ)]
) -> RevenueDifferenceDto:
    svc = RevenueService(session, ctx, now)
    return svc.difference_dtos([svc.difference(difference_id)])[0]


@router.post(
    "/revenue-differences/{difference_id}/explanation",
    response_model=RevenueDifferenceDto,
    operation_id="explainRevenueDifference",
)
@named
def explain_difference(
    difference_id: uuid.UUID,
    body: RevenueExplanationIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(EXPLAIN)],
) -> RevenueDifferenceDto:
    """Propose an explanation (tenant reason + note) for an OPEN difference; a second person decides."""
    return RevenueService(session, ctx, now).explain(difference_id, body)


@router.post(
    "/revenue-differences/{difference_id}/decision",
    response_model=RevenueDifferenceDto,
    operation_id="decideRevenueDifference",
)
@named
def decide_difference(
    difference_id: uuid.UUID,
    body: RevenueDecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(DECIDE)],
) -> RevenueDifferenceDto:
    """APPROVE / REJECT the proposed explanation, or CONFIRM the difference as real. Never by the explainer."""
    return RevenueService(session, ctx, now).decide(difference_id, body)


# --- revenue reasons (tenant list) ------------------------------------------------------------------------------
@router.get("/revenue-reasons", response_model=Page[RevenueReasonDto], operation_id="listRevenueReasons")
def list_reasons(
    session: DbSession,
    _: Annotated[RequestContext, Depends(READ)],
    paging: Paging,
    include_inactive: IncludeInactive = False,
) -> Page[RevenueReasonDto]:
    """Reasons that explain a revenue difference (tenant data; `q`: code or name)."""
    rows, total = paginate(session, RevenueService.reason_query(paging.q, include_inactive), paging)
    return Page(
        items=[RevenueReasonDto.model_validate(r) for r in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get("/revenue-reasons/{reason_id}", response_model=RevenueReasonDto, operation_id="getRevenueReason")
def get_reason(
    reason_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(READ)]
) -> RevenueReasonDto:
    return RevenueReasonDto.model_validate(RevenueService(session, ctx, now).reason(reason_id))


@router.post("/revenue-reasons", response_model=RevenueReasonDto, status_code=201, operation_id="createRevenueReason")
def create_reason(
    body: RevenueReasonIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(DECIDE)]
) -> RevenueReasonDto:
    return RevenueService(session, ctx, now).create_reason(body)


@router.put("/revenue-reasons/{reason_id}", response_model=RevenueReasonDto, operation_id="updateRevenueReason")
def update_reason(
    reason_id: uuid.UUID,
    body: RevenueReasonUpdateIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(DECIDE)],
) -> RevenueReasonDto:
    return RevenueService(session, ctx, now).update_reason(reason_id, body)


@router.post(
    "/revenue-reasons/{reason_id}/deactivate", response_model=RevenueReasonDto, operation_id="deactivateRevenueReason"
)
def deactivate_reason(
    reason_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(DECIDE)],
) -> RevenueReasonDto:
    """Refused for new explanations afterwards; past explanations keep the entry."""
    return RevenueService(session, ctx, now).set_reason_active(reason_id, False, body.reason, body.version)


@router.post(
    "/revenue-reasons/{reason_id}/reactivate", response_model=RevenueReasonDto, operation_id="reactivateRevenueReason"
)
def reactivate_reason(
    reason_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(DECIDE)],
) -> RevenueReasonDto:
    return RevenueService(session, ctx, now).set_reason_active(reason_id, True, body.reason, body.version)


# --- non-revenue time inside jobs: explained by one person, approved by another (owner rule 2026-10-26) -----------
@router.get(
    "/non-revenue-activities", response_model=Page[NonRevenueActivityDto], operation_id="listNonRevenueActivities"
)
@named
def list_non_revenue_activities(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(READ)],
    paging: Paging,
    machine_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    status: Annotated[
        str | None, Query(pattern="^(NONE|PROPOSED|APPROVED|REJECTED)$", description="NONE: not explained yet")
    ] = None,
) -> Page[NonRevenueActivityDto]:
    """Non-billable work-log entries of the declared non-revenue types (e.g. movement), newest first, with their
    approval status. Until APPROVED the time counts as revenue."""
    rows = RevenueService(session, ctx, now).non_revenue_activities(machine_id, job_id, status)
    start = (paging.page - 1) * paging.page_size
    return Page(
        items=rows[start : start + paging.page_size], total=len(rows), page=paging.page, page_size=paging.page_size
    )


@router.get(
    "/non-revenue-approvals", response_model=Page[NonRevenueApprovalDto], operation_id="listNonRevenueApprovals"
)
@named
def list_non_revenue_approvals(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(READ)],
    paging: Paging,
    status: NonRevenueApprovalStatus | None = None,
    machine_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
) -> Page[NonRevenueApprovalDto]:
    svc = RevenueService(session, ctx, now)
    rows, total = paginate(session, svc.approval_query(status, machine_id, job_id), paging)
    return Page(items=svc.approval_dtos(rows), total=total, page=paging.page, page_size=paging.page_size)


@router.get(
    "/non-revenue-approvals/{approval_id}",
    response_model=NonRevenueApprovalDto,
    operation_id="getNonRevenueApproval",
)
@named
def get_non_revenue_approval(
    approval_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(READ)]
) -> NonRevenueApprovalDto:
    svc = RevenueService(session, ctx, now)
    return svc.approval_dtos([svc.approval(approval_id)])[0]


@router.post(
    "/non-revenue-approvals",
    response_model=NonRevenueApprovalDto,
    status_code=201,
    operation_id="proposeNonRevenueApproval",
)
@named
def propose_non_revenue(
    body: NonRevenueApprovalIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(EXPLAIN)]
) -> NonRevenueApprovalDto:
    """Explain a work-log entry as non-revenue (tenant reason + note); a second person with `tenant.revenue.decide`
    approves it."""
    return RevenueService(session, ctx, now).propose_non_revenue(body)


@router.post(
    "/non-revenue-approvals/{approval_id}/decision",
    response_model=NonRevenueApprovalDto,
    operation_id="decideNonRevenueApproval",
)
@named
def decide_non_revenue(
    approval_id: uuid.UUID,
    body: NonRevenueDecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(DECIDE)],
) -> NonRevenueApprovalDto:
    """APPROVE (the time stops counting as revenue; affected revenue differences are recomputed) or REJECT."""
    return RevenueService(session, ctx, now).decide_non_revenue(approval_id, body)
