"""Cash custody chain controls (accountability design C): custodians, field-to-field transfers, float
acknowledgement, variances and write-offs, retentions, custody adjustments, reason lists and the reconciliation
drill-down. Rule switches are the tenant's CASH_CUSTODY policy; approvals are permissions."""

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, NotFound
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.lifecycle import IncludeInactive, LifecycleChangeIn
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.finance.cash_service import CashCustodyService, custody_entry_dto
from asseta.modules.finance.common import resolve_staff
from asseta.modules.finance.custody_dto import (
    CashAcknowledgementIn,
    CashReasonDto,
    CashReasonIn,
    CashReasonUpdateIn,
    CashRetentionDto,
    CashRetentionIn,
    CashTransferDto,
    CashTransferIn,
    CashVarianceDto,
    CustodianDto,
    CustodyAdjustmentDto,
    CustodyAdjustmentIn,
    CustodyTransactionDto,
    DecisionIn,
    ReconciliationFigure,
    VarianceResolutionIn,
    WriteOffProposalIn,
)
from asseta.modules.finance.custody_models import (
    CashDecisionStatus,
    CashReasonKind,
    CashRetention,
    CashTransfer,
    CashTransferStatus,
    CustodyAdjustment,
    VarianceSource,
    VarianceStatus,
)
from asseta.modules.finance.custody_service import CashCustodyControls, custodian_dto
from asseta.modules.finance.dto import CashCustodyEntryDto
from asseta.modules.finance.permissions import (
    ADJUSTMENT_APPROVE,
    CASH_OFFICE,
    COLLECT,
    CUSTODY_READ,
    CUSTODY_RECORD,
    FINANCE_READ,
    REASON_MANAGE,
    RETENTION_APPROVE,
    VARIANCE,
    WRITEOFF,
)
from asseta.modules.identity.principal import RequestContext

router = APIRouter(prefix="/api/v1/tenant/cash", tags=["finance"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
IdemKey = Annotated[str | None, Header()]
Paging = Annotated[PageParams, Depends(page_params)]
Currency = Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")]


def _page[T](items: list[T], total: int, paging: PageParams) -> Page[T]:
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


# --- custodians -----------------------------------------------------------------------------------------------
@router.get("/custodians", response_model=Page[CustodianDto], operation_id="listCashCustodians")
def list_custodians(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CUSTODY_READ)],
    paging: Paging,
    include_inactive: IncludeInactive = False,
) -> Page[CustodianDto]:
    """Staff who can hold company cash (any active staff member; a login is not required). Search by name/code."""
    stmt = CashCustodyControls(session, ctx, now).custodians(paging.q, include_inactive)
    rows, total = paginate(session, stmt, paging)
    return _page([custodian_dto(s) for s in rows], total, paging)


# --- transfers ------------------------------------------------------------------------------------------------
@router.post("/transfers", response_model=CashTransferDto, status_code=201, operation_id="recordCashTransfer")
def record_transfer(
    body: CashTransferIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(COLLECT)],
    idempotency_key: IdemKey = None,
) -> CashTransferDto:
    """Field-to-field transfer (never a company receipt). Pending the receiver's acknowledgement unless the tenant
    does not require one, or the recorder is the receiver and the tenant counts that as acknowledgement."""
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "recordCashTransfer", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return CashTransferDto.model_validate(replay)
    dto = CashCustodyControls(session, ctx, now).record_transfer(body)
    guard.complete(dto, 201)
    return dto


@router.get("/transfers", response_model=Page[CashTransferDto], operation_id="listCashTransfers")
def list_transfers(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CUSTODY_READ)],
    paging: Paging,
    status: CashTransferStatus | None = None,
    staff_member_id: uuid.UUID | None = None,
) -> Page[CashTransferDto]:
    svc = CashCustodyControls(session, ctx, now)
    rows, total = paginate(session, svc.list_transfers(status, staff_member_id), paging)
    return _page([svc.transfer_dto(t) for t in rows], total, paging)


@router.get("/transfers/{transfer_id}", response_model=CashTransferDto, operation_id="getCashTransfer")
def get_transfer(
    transfer_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(CUSTODY_READ)]
) -> CashTransferDto:
    svc = CashCustodyControls(session, ctx, now)
    row = session.execute(
        svc.list_transfers(None, None).where(CashTransfer.id == transfer_id)
    ).scalar_one_or_none()  # only transfers the caller may see
    if row is None:
        raise NotFound("Transfer not found", code="TRANSFER_NOT_FOUND")
    return svc.transfer_dto(row)


@router.post(
    "/transfers/{transfer_id}/acknowledgement",
    response_model=CashTransferDto,
    operation_id="acknowledgeCashTransfer",
)
def acknowledge_transfer(
    transfer_id: uuid.UUID,
    body: CashAcknowledgementIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(COLLECT)],
) -> CashTransferDto:
    """The receiver (or, when the tenant allows, a recorder on their behalf) acknowledges the amount actually
    received or disputes the transfer. Never the sender; a different amount opens a cash variance."""
    return CashCustodyControls(session, ctx, now).acknowledge_transfer(transfer_id, body)


# --- floats ---------------------------------------------------------------------------------------------------
@router.get("/floats", response_model=Page[CashCustodyEntryDto], operation_id="listCashFloats")
def list_floats(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CUSTODY_READ)],
    paging: Paging,
    staff_member_id: uuid.UUID | None = None,
    awaiting_acknowledgement: bool | None = None,
) -> Page[CashCustodyEntryDto]:
    """Floats (and opening balances) with their acknowledgement state. Field recorders see their own unless the
    tenant lets them record on custodians' behalf."""
    svc = CashCustodyControls(session, ctx, now)
    rows, total = paginate(session, svc.list_floats(staff_member_id, awaiting_acknowledgement), paging)
    return _page([custody_entry_dto(e, svc.float_ack(e.id)) for e in rows], total, paging)


@router.post(
    "/floats/{entry_id}/acknowledgement", response_model=CashCustodyEntryDto, operation_id="acknowledgeCashFloat"
)
def acknowledge_float(
    entry_id: uuid.UUID,
    body: CashAcknowledgementIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(COLLECT)],
) -> CashCustodyEntryDto:
    """Acknowledge (amount actually received) or dispute a float that the tenant requires to be acknowledged. Until
    then it does not count in the receiver's custody."""
    return CashCustodyControls(session, ctx, now).acknowledge_float(entry_id, body)


# --- variances ------------------------------------------------------------------------------------------------
@router.get("/variances", response_model=Page[CashVarianceDto], operation_id="listCashVariances")
def list_variances(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(FINANCE_READ)],
    paging: Paging,
    status: VarianceStatus | None = None,
    staff_member_id: uuid.UUID | None = None,
    source_type: VarianceSource | None = None,
) -> Page[CashVarianceDto]:
    stmt = CashCustodyControls(session, ctx, now).list_variances(status, staff_member_id, source_type)
    rows, total = paginate(session, stmt, paging)
    return _page([CashVarianceDto.model_validate(v) for v in rows], total, paging)


@router.get("/variances/{variance_id}", response_model=CashVarianceDto, operation_id="getCashVariance")
def get_variance(
    variance_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(FINANCE_READ)]
) -> CashVarianceDto:
    return CashVarianceDto.model_validate(CashCustodyControls(session, ctx, now).variance(variance_id))


@router.post("/variances/{variance_id}/resolution", response_model=CashVarianceDto, operation_id="resolveCashVariance")
def resolve_variance(
    variance_id: uuid.UUID,
    body: VarianceResolutionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(VARIANCE)],
) -> CashVarianceDto:
    """Resolve an open variance as RECOVERED or CORRECTED_ERROR (reason required). WRITTEN_OFF directly only when
    the tenant does not require write-off approval, and then only with the write-off permission."""
    return CashCustodyControls(session, ctx, now).resolve_variance(variance_id, body)


@router.post(
    "/variances/{variance_id}/write-off-proposal",
    response_model=CashVarianceDto,
    operation_id="proposeCashVarianceWriteOff",
)
def propose_writeoff(
    variance_id: uuid.UUID,
    body: WriteOffProposalIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(VARIANCE)],
) -> CashVarianceDto:
    return CashCustodyControls(session, ctx, now).propose_writeoff(variance_id, body)


@router.post(
    "/variances/{variance_id}/write-off-decision",
    response_model=CashVarianceDto,
    operation_id="decideCashVarianceWriteOff",
)
def decide_writeoff(
    variance_id: uuid.UUID,
    body: DecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(WRITEOFF)],
) -> CashVarianceDto:
    """Approve (resolves as WRITTEN_OFF; the accountable custodian's expected balance drops by the difference) or
    reject (back to OPEN) a proposed write-off. Never by the proposer."""
    return CashCustodyControls(session, ctx, now).decide_writeoff(variance_id, body)


# --- retentions -----------------------------------------------------------------------------------------------
@router.post("/retentions", response_model=CashRetentionDto, status_code=201, operation_id="requestCashRetention")
def request_retention(
    body: CashRetentionIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(CUSTODY_RECORD)]
) -> CashRetentionDto:
    """Ask that a custodian may keep some cash instead of remitting it (exception to full remittance)."""
    return CashCustodyControls(session, ctx, now).request_retention(body)


@router.get("/retentions", response_model=Page[CashRetentionDto], operation_id="listCashRetentions")
def list_retentions(
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(CUSTODY_READ)],
    paging: Paging,
    status: CashDecisionStatus | None = None,
    staff_member_id: uuid.UUID | None = None,
) -> Page[CashRetentionDto]:
    stmt = select(CashRetention).order_by(CashRetention.created_at.desc(), CashRetention.id)
    if status:
        stmt = stmt.where(CashRetention.status == status)
    if staff_member_id:
        stmt = stmt.where(CashRetention.staff_member_id == staff_member_id)
    rows, total = paginate(session, stmt, paging)
    return _page([CashRetentionDto.model_validate(r) for r in rows], total, paging)


@router.post("/retentions/{retention_id}/decision", response_model=CashRetentionDto, operation_id="decideCashRetention")
def decide_retention(
    retention_id: uuid.UUID,
    body: DecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(RETENTION_APPROVE)],
) -> CashRetentionDto:
    return CashCustodyControls(session, ctx, now).decide_retention(retention_id, body)


# --- custody adjustments --------------------------------------------------------------------------------------
@router.post(
    "/adjustments", response_model=CustodyAdjustmentDto, status_code=201, operation_id="proposeCustodyAdjustment"
)
def propose_adjustment(
    body: CustodyAdjustmentIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(CASH_OFFICE)]
) -> CustodyAdjustmentDto:
    """Propose a reversal or adjustment of a custodian's expected balance (reason required); counts once approved
    by someone else."""
    return CashCustodyControls(session, ctx, now).propose_adjustment(body)


@router.get("/adjustments", response_model=Page[CustodyAdjustmentDto], operation_id="listCustodyAdjustments")
def list_adjustments(
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(FINANCE_READ)],
    paging: Paging,
    status: CashDecisionStatus | None = None,
    staff_member_id: uuid.UUID | None = None,
) -> Page[CustodyAdjustmentDto]:
    stmt = select(CustodyAdjustment).order_by(CustodyAdjustment.created_at.desc(), CustodyAdjustment.id)
    if status:
        stmt = stmt.where(CustodyAdjustment.status == status)
    if staff_member_id:
        stmt = stmt.where(CustodyAdjustment.staff_member_id == staff_member_id)
    rows, total = paginate(session, stmt, paging)
    return _page([CustodyAdjustmentDto.model_validate(r) for r in rows], total, paging)


@router.post(
    "/adjustments/{adjustment_id}/decision",
    response_model=CustodyAdjustmentDto,
    operation_id="decideCustodyAdjustment",
)
def decide_adjustment(
    adjustment_id: uuid.UUID,
    body: DecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(ADJUSTMENT_APPROVE)],
) -> CustodyAdjustmentDto:
    return CashCustodyControls(session, ctx, now).decide_adjustment(adjustment_id, body)


# --- reason lists ---------------------------------------------------------------------------------------------
@router.get("/reasons", response_model=Page[CashReasonDto], operation_id="listCashReasons")
def list_reasons(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CUSTODY_READ)],
    paging: Paging,
    kind: CashReasonKind | None = None,
    include_inactive: IncludeInactive = False,
) -> Page[CashReasonDto]:
    stmt = CashCustodyControls(session, ctx, now).list_reasons(kind, paging.q, include_inactive)
    rows, total = paginate(session, stmt, paging)
    return _page([CashReasonDto.model_validate(r) for r in rows], total, paging)


@router.post("/reasons", response_model=CashReasonDto, status_code=201, operation_id="createCashReason")
def create_reason(
    body: CashReasonIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(REASON_MANAGE)]
) -> CashReasonDto:
    return CashCustodyControls(session, ctx, now).create_reason(body)


@router.get("/reasons/{reason_id}", response_model=CashReasonDto, operation_id="getCashReason")
def get_reason(
    reason_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(CUSTODY_READ)]
) -> CashReasonDto:
    return CashReasonDto.model_validate(CashCustodyControls(session, ctx, now).reason(reason_id))


@router.patch("/reasons/{reason_id}", response_model=CashReasonDto, operation_id="updateCashReason")
def update_reason(
    reason_id: uuid.UUID,
    body: CashReasonUpdateIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REASON_MANAGE)],
) -> CashReasonDto:
    return CashCustodyControls(session, ctx, now).update_reason(reason_id, body)


@router.post("/reasons/{reason_id}/deactivate", response_model=CashReasonDto, operation_id="deactivateCashReason")
def deactivate_reason(
    reason_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REASON_MANAGE)],
) -> CashReasonDto:
    return CashCustodyControls(session, ctx, now).set_reason_active(reason_id, body, active=False)


@router.post("/reasons/{reason_id}/reactivate", response_model=CashReasonDto, operation_id="reactivateCashReason")
def reactivate_reason(
    reason_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REASON_MANAGE)],
) -> CashReasonDto:
    return CashCustodyControls(session, ctx, now).set_reason_active(reason_id, body, active=True)


# --- reconciliation drill-down --------------------------------------------------------------------------------
Figures = Annotated[list[ReconciliationFigure] | None, Query(description="Only these figures (default: all)")]


@router.get(
    "/reconciliation/transactions",
    response_model=Page[CustodyTransactionDto],
    operation_id="listCashReconciliationTransactions",
)
def reconciliation_transactions(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(FINANCE_READ)],
    paging: Paging,
    staff_member_id: uuid.UUID,
    period_from: Annotated[date, Query(alias="from")],
    period_to: Annotated[date, Query(alias="to")],
    currency: Currency = None,
    figure: Figures = None,
) -> Page[CustodyTransactionDto]:
    """The transactions behind each reconciliation figure of a custodian over the period (tenant-local days), with
    the record (entity_type/entity_id) holding its evidence. Latest first."""
    rows = CashCustodyService(session, ctx, now).transactions(staff_member_id, currency, period_from, period_to, figure)
    start = (paging.page - 1) * paging.page_size
    return _page(rows[start : start + paging.page_size], len(rows), paging)


@router.get(
    "/custody/me/reconciliation/transactions",
    response_model=Page[CustodyTransactionDto],
    operation_id="listMyCashReconciliationTransactions",
)
def my_reconciliation_transactions(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(COLLECT)],
    paging: Paging,
    period_from: Annotated[date, Query(alias="from")],
    period_to: Annotated[date, Query(alias="to")],
    currency: Currency = None,
    figure: Figures = None,
) -> Page[CustodyTransactionDto]:
    """The caller's own custody transactions behind each reconciliation figure."""
    own = resolve_staff(session, ctx, None, require_active=False)
    rows = CashCustodyService(session, ctx, now).transactions(own.id, currency, period_from, period_to, figure)
    start = (paging.page - 1) * paging.page_size
    return _page(rows[start : start + paging.page_size], len(rows), paging)
