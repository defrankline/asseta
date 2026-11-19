"""Machine report endpoints (ADR-008 §2, tenant scope). The request and response shapes, error codes and the offline
operation are described for the web and phone teams in docs/api-machine-reports.md."""

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, NotFound
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.lifecycle import LifecycleChangeIn
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.accountability.names import named
from asseta.modules.finance.common import period_conditions
from asseta.modules.identity.principal import RequestContext
from asseta.modules.machine_reports.dto import (
    AvailableHoursDto,
    MachineReportContextDto,
    MachineReportDecisionIn,
    MachineReportDto,
    MachineReportIn,
    MachineReportReasonDto,
    MachineReportReasonIn,
    MachineReportRejectIn,
    MachineReportStatusDto,
)
from asseta.modules.machine_reports.models import MachineReport, MachineReportStatus
from asseta.modules.machine_reports.permissions import APPROVE, CONTEXT, READ, REASONS, REASONS_READ, SUBMIT
from asseta.modules.machine_reports.service import MachineReportService, report_query
from asseta.modules.meter.engine_dto import EngineHourReasonIn, EngineHourReasonUpdateIn
from asseta.modules.meter.engine_models import EngineHourReasonKind
from asseta.modules.meter.engine_service import EngineHoursService

router = APIRouter(prefix="/api/v1/tenant", tags=["machine-reports"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
IdemKey = Annotated[str | None, Header()]
Paging = Annotated[PageParams, Depends(page_params)]
Read = Annotated[RequestContext, Depends(READ)]


@router.post("/machine-reports", response_model=MachineReportDto, status_code=201, operation_id="submitMachineReport")
@named
def submit_report(
    body: MachineReportIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(SUBMIT)],
    idempotency_key: IdemKey = None,
) -> MachineReportDto:
    """Submit a report: the new reading and how its hours split across customers and non-productive reasons. The
    customers' hours are reserved until an approver decides."""
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "submitMachineReport", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return MachineReportDto.model_validate(replay)
    dto = MachineReportService(session, ctx, now).submit(body)
    guard.complete(dto, 201)
    return dto


@router.get("/machine-reports", response_model=Page[MachineReportDto], operation_id="listMachineReports")
@named
def list_reports(
    session: DbSession,
    now: Now,
    ctx: Read,
    paging: Paging,
    machine_id: uuid.UUID | None = None,
    status: MachineReportStatus | None = None,
    queue: Annotated[
        str | None, Query(pattern="^PENDING$", description="PENDING: reports waiting for a decision (SUBMITTED)")
    ] = None,
    customer_id: uuid.UUID | None = None,
    mine: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Page[MachineReportDto]:
    """Machine reports, newest first (`q`: report number or machine). Field users see their own reports and those on
    machines assigned to them; approvers see all. `queue=PENDING` is the approval queue; dates filter submission."""
    assert ctx.tenant_id is not None
    period = period_conditions(session, ctx.tenant_id, MachineReport.submitted_at, date_from, date_to)
    stmt = report_query(
        session,
        ctx,
        q=paging.q,
        machine_id=machine_id,
        status=MachineReportStatus.SUBMITTED if queue == "PENDING" else status,
        customer_id=customer_id,
        submitted_by=ctx.user_id if mine else None,
        period=list(period),
    )
    rows, total = paginate(session, stmt, paging)
    items = MachineReportService(session, ctx, now).dtos(list(rows))
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


@router.get(
    "/machine-reports/status", response_model=list[MachineReportStatusDto], operation_id="listMachineReportStatus"
)
@named
def report_status(
    session: DbSession, now: Now, ctx: Read, machine_id: Annotated[list[uuid.UUID] | None, Query()] = None
) -> list[MachineReportStatusDto]:
    """Each machine's report status: last approved reading, pending report, days since the last report (field users:
    their assigned machines)."""
    return MachineReportService(session, ctx, now).statuses(machine_id)


@router.get(
    "/machine-reports/context/{machine_id}",
    response_model=MachineReportContextDto,
    operation_id="getMachineReportContext",
)
@named
def report_context(
    machine_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(CONTEXT)]
) -> MachineReportContextDto:
    """What a new report on the machine starts from: previous reading, pending report, customers with available
    hours and the reason list."""
    return MachineReportService(session, ctx, now).context(machine_id)


@router.get("/machine-reports/available-hours", response_model=list[AvailableHoursDto], operation_id="listReportHours")
@named
def available(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CONTEXT)],
    machine_id: uuid.UUID,
    customer_id: Annotated[list[uuid.UUID] | None, Query()] = None,
) -> list[AvailableHoursDto]:
    """Customers' hours a new report on the machine may draw on (activated - used - reserved by SUBMITTED reports)."""
    return MachineReportService(session, ctx, now).available(machine_id, customer_id)


@router.get("/machine-reports/{report_id}", response_model=MachineReportDto, operation_id="getMachineReport")
@named
def get_report(report_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> MachineReportDto:
    """A report with its lines, the reading's findings and the tracker cross-check (approver aid)."""
    svc = MachineReportService(session, ctx, now)
    return svc.dto(svc.report(report_id))


@router.post(
    "/machine-reports/{report_id}/approve", response_model=MachineReportDto, operation_id="approveMachineReport"
)
@named
def approve_report(
    report_id: uuid.UUID,
    body: MachineReportDecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(APPROVE)],
) -> MachineReportDto:
    """Approve (never your own): consumes the customers' hours FIFO and writes the allocation ledger."""
    return MachineReportService(session, ctx, now).approve(report_id, body)


@router.post("/machine-reports/{report_id}/reject", response_model=MachineReportDto, operation_id="rejectMachineReport")
@named
def reject_report(
    report_id: uuid.UUID,
    body: MachineReportRejectIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(APPROVE)],
) -> MachineReportDto:
    """Reject with a reason (never your own): the reservation is released. The rejection is final: the report stays as
    a record and the supervisor sends a new report with a new reading."""
    return MachineReportService(session, ctx, now).reject(report_id, body)


# --- the reason list (one of the engine-hour reason lists, kind NON_PRODUCTIVE) -----------------------------------
@router.get(
    "/machine-report-reasons", response_model=list[MachineReportReasonDto], operation_id="listMachineReportReasons"
)
def list_reasons(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REASONS_READ)],
    include_inactive: bool = False,
) -> list[MachineReportReasonDto]:
    return MachineReportService(session, ctx, now).reasons(include_inactive)


@router.post(
    "/machine-report-reasons",
    response_model=MachineReportReasonDto,
    status_code=201,
    operation_id="createMachineReportReason",
)
def create_reason(
    body: MachineReportReasonIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REASONS)],
) -> MachineReportReasonDto:
    reason = EngineHourReasonIn(
        kind=EngineHourReasonKind.NON_PRODUCTIVE, code=body.code, name=body.name, description=body.description
    )
    return MachineReportReasonDto.model_validate(
        EngineHoursService(session, ctx, now).create_reason(reason).model_dump()
    )


@router.put(
    "/machine-report-reasons/{reason_id}",
    response_model=MachineReportReasonDto,
    operation_id="updateMachineReportReason",
)
def update_reason(
    reason_id: uuid.UUID,
    body: EngineHourReasonUpdateIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REASONS)],
) -> MachineReportReasonDto:
    svc = EngineHoursService(session, ctx, now)
    _own_reason(svc, reason_id)
    return MachineReportReasonDto.model_validate(svc.update_reason(reason_id, body).model_dump())


@router.post(
    "/machine-report-reasons/{reason_id}/deactivate",
    response_model=MachineReportReasonDto,
    operation_id="deactivateMachineReportReason",
)
def deactivate_reason(
    reason_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REASONS)],
) -> MachineReportReasonDto:
    svc = EngineHoursService(session, ctx, now)
    _own_reason(svc, reason_id)
    return MachineReportReasonDto.model_validate(
        svc.set_reason_active(reason_id, False, body.reason, body.version).model_dump()
    )


@router.post(
    "/machine-report-reasons/{reason_id}/reactivate",
    response_model=MachineReportReasonDto,
    operation_id="reactivateMachineReportReason",
)
def reactivate_reason(
    reason_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REASONS)],
) -> MachineReportReasonDto:
    svc = EngineHoursService(session, ctx, now)
    _own_reason(svc, reason_id)
    return MachineReportReasonDto.model_validate(
        svc.set_reason_active(reason_id, True, body.reason, body.version).model_dump()
    )


def _own_reason(svc: EngineHoursService, reason_id: uuid.UUID) -> None:

    if svc.reason(reason_id).kind is not EngineHourReasonKind.NON_PRODUCTIVE:
        raise NotFound("Reason not found")
