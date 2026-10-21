"""Supervisor cash custody: floats, cash collections, handovers (claimed -> verified) and daily reconciliation."""

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.dto import (
    CashCollectionIn,
    CashCustodyBalanceDto,
    CashCustodyEntryDto,
    CashFloatIn,
    CashHandoverDto,
    CashHandoverIn,
    CashReconciliationDto,
    CustomerPaymentDto,
    SettlementDecisionIn,
)
from asseta.modules.finance.models import CashHandover, SettlementStatus
from asseta.modules.finance.permissions import CASH_OFFICE, COLLECT, FINANCE_READ, VERIFY
from asseta.modules.identity.principal import RequestContext

router = APIRouter(prefix="/api/v1/tenant/cash", tags=["finance"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
IdemKey = Annotated[str | None, Header()]


@router.post("/floats", response_model=CashCustodyEntryDto, status_code=201, operation_id="issueCashFloat")
def issue_float(
    body: CashFloatIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CASH_OFFICE)],
    idempotency_key: IdemKey = None,
) -> CashCustodyEntryDto:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "issueCashFloat", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return CashCustodyEntryDto.model_validate(replay)
    dto = CashCustodyService(session, ctx, now).issue_float(body)
    guard.complete(dto, 201)
    return dto


@router.post("/collections", response_model=CustomerPaymentDto, status_code=201, operation_id="recordCashCollection")
def record_collection(
    body: CashCollectionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(COLLECT)],
    idempotency_key: IdemKey = None,
) -> CustomerPaymentDto:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "recordCashCollection", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return CustomerPaymentDto.model_validate(replay)
    dto = CashCustodyService(session, ctx, now).record_collection(body)
    guard.complete(dto, 201)
    return dto


@router.post("/handovers", response_model=CashHandoverDto, status_code=201, operation_id="recordCashHandover")
def record_handover(
    body: CashHandoverIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(COLLECT)],
    idempotency_key: IdemKey = None,
) -> CashHandoverDto:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "recordCashHandover", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return CashHandoverDto.model_validate(replay)
    dto = CashCustodyService(session, ctx, now).record_handover(body)
    guard.complete(dto, 201)
    return dto


@router.get("/handovers", response_model=Page[CashHandoverDto], operation_id="listCashHandovers")
def list_handovers(
    session: DbSession,
    _: Annotated[RequestContext, Depends(FINANCE_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    status: SettlementStatus | None = None,
    staff_member_id: uuid.UUID | None = None,
) -> Page[CashHandoverDto]:
    stmt = select(CashHandover).order_by(CashHandover.handed_at.desc())
    if status:
        stmt = stmt.where(CashHandover.status == status)
    if staff_member_id:
        stmt = stmt.where(CashHandover.staff_member_id == staff_member_id)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[CashHandoverDto.model_validate(h) for h in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.post("/handovers/{handover_id}/decision", response_model=CashHandoverDto, operation_id="decideCashHandover")
def decide_handover(
    handover_id: uuid.UUID,
    body: SettlementDecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(VERIFY)],
) -> CashHandoverDto:
    return CashCustodyService(session, ctx, now).decide_handover(handover_id, body)


@router.get("/reconciliation", response_model=CashReconciliationDto, operation_id="getCashReconciliation")
def reconciliation(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(FINANCE_READ)],
    staff_member_id: uuid.UUID,
    period_from: Annotated[date, Query(alias="from")],
    period_to: Annotated[date, Query(alias="to")],
    currency: Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")] = None,
) -> CashReconciliationDto:
    return CashCustodyService(session, ctx, now).reconciliation(staff_member_id, currency, period_from, period_to)


@router.get("/custody", response_model=list[CashCustodyBalanceDto], operation_id="getCashCustody")
def custody(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(FINANCE_READ)],
    staff_member_id: uuid.UUID,
) -> list[CashCustodyBalanceDto]:
    return CashCustodyService(session, ctx, now).balances(staff_member_id)


@router.get("/custody/me", response_model=list[CashCustodyBalanceDto], operation_id="getMyCashCustody")
def my_custody(
    session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(COLLECT)]
) -> list[CashCustodyBalanceDto]:
    return CashCustodyService(session, ctx, now).balances(None)
