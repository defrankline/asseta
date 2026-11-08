"""Finance -> Adjustments ledger (Ledger 6) and the uniform propose/decide flow for corrections, refunds, reversals."""

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.accountability.names import fill_names, named
from asseta.modules.adjustments.dto import (
    AdjustmentDecisionIn,
    AdjustmentEntryDto,
    AdjustmentPreviewDto,
    AdjustmentPreviewIn,
    AdjustmentRequestDto,
    AdjustmentRequestIn,
    AdjustmentWithdrawIn,
)
from asseta.modules.adjustments.models import (
    AdjustmentEntryStatus,
    AdjustmentRequestStatus,
    AdjustmentRequestType,
    AdjustmentType,
)
from asseta.modules.adjustments.permissions import ADJUSTMENT_DECIDE, ADJUSTMENT_PROPOSE, ADJUSTMENT_READ
from asseta.modules.adjustments.requests import AdjustmentRequests
from asseta.modules.adjustments.service import AdjustmentLedger, entries_csv
from asseta.modules.identity.principal import RequestContext

router = APIRouter(prefix="/api/v1/tenant", tags=["adjustments"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
Reader = Annotated[RequestContext, Depends(ADJUSTMENT_READ)]
Proposer = Annotated[RequestContext, Depends(ADJUSTMENT_PROPOSE)]
Decider = Annotated[RequestContext, Depends(ADJUSTMENT_DECIDE)]
Q = Annotated[str | None, Query(max_length=100)]
Type_ = Annotated[AdjustmentType | None, Query(alias="type")]
Reference = Annotated[str | None, Query(max_length=120)]
Day = Annotated[date | None, Query()]


def _tid(ctx: RequestContext) -> uuid.UUID:
    assert ctx.tenant_id is not None
    return ctx.tenant_id


@router.get("/adjustments", response_model=Page[AdjustmentEntryDto], operation_id="listAdjustments")
@named
def list_adjustments(
    session: DbSession,
    ctx: Reader,
    paging: Annotated[PageParams, Depends(page_params)],
    type_: Type_ = None,
    status: AdjustmentEntryStatus | None = None,
    person_id: uuid.UUID | None = None,
    date_from: Day = None,
    date_to: Day = None,
    machine_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    staff_member_id: uuid.UUID | None = None,
    reference: Reference = None,
    original_id: uuid.UUID | None = None,
) -> Page[AdjustmentEntryDto]:
    """Filters: `type` (AdjustmentType), `status`, `person_id` (requester or approver), `date_from`/`date_to`
    (tenant-local days, posting date), `machine_id`, `customer_id`, `staff_member_id`, `reference` (original
    reference, contains), `original_id`, `q` (reference, reason)."""
    stmt = AdjustmentLedger(session, _tid(ctx)).query(
        paging.q,
        type_,
        status,
        person_id,
        date_from,
        date_to,
        machine_id,
        customer_id,
        staff_member_id,
        reference,
        original_id,
    )
    rows, total = paginate(session, stmt, paging)
    return Page[AdjustmentEntryDto](
        items=[AdjustmentEntryDto.model_validate(r) for r in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get(
    "/adjustments/export.csv",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/csv": {}}}},
    operation_id="exportAdjustmentsCsv",
)
def export_adjustments(
    session: DbSession,
    ctx: Reader,
    q: Q = None,
    type_: Type_ = None,
    status: AdjustmentEntryStatus | None = None,
    person_id: uuid.UUID | None = None,
    date_from: Day = None,
    date_to: Day = None,
    machine_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    staff_member_id: uuid.UUID | None = None,
    reference: Reference = None,
) -> StreamingResponse:
    """The list's rows (same filters, no paging) as CSV."""
    stmt = AdjustmentLedger(session, _tid(ctx)).query(
        q, type_, status, person_id, date_from, date_to, machine_id, customer_id, staff_member_id, reference, None
    )
    rows = fill_names(session, [AdjustmentEntryDto.model_validate(r) for r in session.execute(stmt).scalars()])
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="adjustment.ledger.exported",
        entity_type="adjustment_ledger_entry",
        entity_id=_tid(ctx),
        tenant_id=_tid(ctx),
        after={"rows": len(rows), "type": type_.value if type_ else None},
    )
    return StreamingResponse(
        iter([entries_csv(rows)]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="asseta-adjustments.csv"', "Cache-Control": "no-store"},
    )


@router.get("/adjustments/{entry_id}", response_model=AdjustmentEntryDto, operation_id="getAdjustment")
@named
def get_adjustment(entry_id: uuid.UUID, session: DbSession, ctx: Reader) -> AdjustmentEntryDto:
    return AdjustmentEntryDto.model_validate(AdjustmentLedger(session, _tid(ctx)).entry(entry_id))


@router.get("/adjustment-requests", response_model=Page[AdjustmentRequestDto], operation_id="listAdjustmentRequests")
@named
def list_requests(
    session: DbSession,
    now: Now,
    ctx: Reader,
    paging: Annotated[PageParams, Depends(page_params)],
    request_type: AdjustmentRequestType | None = None,
    status: AdjustmentRequestStatus | None = None,
    customer_id: uuid.UUID | None = None,
    machine_id: uuid.UUID | None = None,
    original_id: uuid.UUID | None = None,
) -> Page[AdjustmentRequestDto]:
    svc = AdjustmentRequests(session, ctx, now)
    rows, total = paginate(
        session, svc.query(paging.q, request_type, status, customer_id, machine_id, original_id), paging
    )
    return Page[AdjustmentRequestDto](
        items=[svc.dto(r) for r in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.post(
    "/adjustment-requests", response_model=AdjustmentRequestDto, status_code=201, operation_id="proposeAdjustment"
)
@named
def propose_adjustment(body: AdjustmentRequestIn, session: DbSession, now: Now, ctx: Proposer) -> AdjustmentRequestDto:
    """Propose a correction, refund, reversal or invoice void; someone else decides it. HOURS_CORRECTION: `purchase_id`,
    optional `machine_id` (the purchase's machine by default), signed `hours`, optional `job_id` / `consumed_entry_id`.
    HOURS_REFUND: `purchase_id`, `machine_id`, positive `hours`, `settlement` (CREDIT | PAY_OUT, with `payout`).
    PAYMENT_REVERSAL / COLLECTION_REVERSAL: `payment_id`. PURCHASE_REVERSAL: `purchase_id`.
    INVOICE_VOID: `invoice_id`."""
    return AdjustmentRequests(session, ctx, now).propose(body)


@router.post("/adjustment-requests/preview", response_model=AdjustmentPreviewDto, operation_id="previewAdjustment")
@named
def preview(body: AdjustmentPreviewIn, session: DbSession, now: Now, ctx: Proposer) -> AdjustmentPreviewDto:
    """What this request would do, as of now, without saving it: the same fields and checks as proposing it, and the
    same `effects` forecast the decider will see. Reason and evidence are not needed yet."""
    return AdjustmentRequests(session, ctx, now).preview(body)


@router.get(
    "/adjustment-requests/{request_id}", response_model=AdjustmentRequestDto, operation_id="getAdjustmentRequest"
)
@named
def get_request(request_id: uuid.UUID, session: DbSession, now: Now, ctx: Reader) -> AdjustmentRequestDto:
    svc = AdjustmentRequests(session, ctx, now)
    return svc.dto(svc.row(request_id))


@router.post(
    "/adjustment-requests/{request_id}/decision",
    response_model=AdjustmentRequestDto,
    operation_id="decideAdjustmentRequest",
)
@named
def decide_request(
    request_id: uuid.UUID, body: AdjustmentDecisionIn, session: DbSession, now: Now, ctx: Decider
) -> AdjustmentRequestDto:
    return AdjustmentRequests(session, ctx, now).decide(request_id, body)


@router.post(
    "/adjustment-requests/{request_id}/withdraw",
    response_model=AdjustmentRequestDto,
    operation_id="withdrawAdjustmentRequest",
)
@named
def withdraw_request(
    request_id: uuid.UUID, body: AdjustmentWithdrawIn, session: DbSession, now: Now, ctx: Proposer
) -> AdjustmentRequestDto:
    return AdjustmentRequests(session, ctx, now).withdraw(request_id, body.reason)
