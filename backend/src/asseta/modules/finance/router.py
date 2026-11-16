"""Tenant customer payments, balances and statements (on credit invoices) and profitability (tenant scope only;
platform scope never reaches these routes or rows)."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.core.search import ilike_any
from asseta.modules.accountability.names import named
from asseta.modules.finance.common import period_conditions
from asseta.modules.finance.dto import (
    CustomerBalanceDto,
    CustomerPaymentDto,
    CustomerPaymentIn,
    CustomerStatementDto,
    ProfitabilityDto,
    SettlementDecisionIn,
)
from asseta.modules.finance.models import CustomerPayment, HirePaymentMethod, SettlementStatus
from asseta.modules.finance.payment_service import CustomerPaymentService, payment_dto
from asseta.modules.finance.permissions import (
    FINANCE_READ,
    PAYMENT_DETAIL_READ,
    PAYMENT_WRITE,
    REPORT,
    VERIFY,
)
from asseta.modules.finance.profitability import ProfitabilityService
from asseta.modules.finance.receivables import ReceivablesService
from asseta.modules.identity.principal import RequestContext

router = APIRouter(prefix="/api/v1/tenant", tags=["finance"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
IdemKey = Annotated[str | None, Header()]


@router.post(
    "/customer-payments", response_model=CustomerPaymentDto, status_code=201, operation_id="recordCustomerPayment"
)
@named
def record_payment(
    body: CustomerPaymentIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(PAYMENT_WRITE)],
    idempotency_key: IdemKey = None,
) -> CustomerPaymentDto:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "recordCustomerPayment", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return CustomerPaymentDto.model_validate(replay)
    dto = CustomerPaymentService(session, ctx, now).record(body)
    guard.complete(dto, 201)
    return dto


@router.get("/customer-payments", response_model=Page[CustomerPaymentDto], operation_id="listCustomerPayments")
@named
def list_payments(
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(FINANCE_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    status: SettlementStatus | None = None,
    customer_id: uuid.UUID | None = None,
    staff_member_id: uuid.UUID | None = None,
    method: HirePaymentMethod | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Page[CustomerPaymentDto]:
    assert ctx.tenant_id is not None
    period = period_conditions(session, ctx.tenant_id, CustomerPayment.received_at, date_from, date_to)
    stmt = select(CustomerPayment).where(*period).order_by(CustomerPayment.received_at.desc())
    if method:
        stmt = stmt.where(CustomerPayment.method == method)
    if status:
        stmt = stmt.where(CustomerPayment.status == status)
    if customer_id:
        stmt = stmt.where(CustomerPayment.customer_id == customer_id)
    if staff_member_id:
        stmt = stmt.where(CustomerPayment.received_by_staff_id == staff_member_id)
    if (match := ilike_any(paging.q, CustomerPayment.collection_number, CustomerPayment.reference)) is not None:
        stmt = stmt.where(match)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[payment_dto(session, p) for p in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.post(
    "/customer-payments/{payment_id}/decision", response_model=CustomerPaymentDto, operation_id="decideCustomerPayment"
)
@named
def decide_payment(
    payment_id: uuid.UUID,
    body: SettlementDecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(VERIFY)],
) -> CustomerPaymentDto:
    return CustomerPaymentService(session, ctx, now).decide(payment_id, body)


@router.get("/customer-payments/{payment_id}", response_model=CustomerPaymentDto, operation_id="getCustomerPayment")
@named
def get_payment(
    payment_id: uuid.UUID,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(PAYMENT_DETAIL_READ)],
) -> CustomerPaymentDto:
    return payment_dto(session, CustomerPaymentService(session, ctx, now).payment(payment_id))


@router.get(
    "/customers/{customer_id}/balance", response_model=list[CustomerBalanceDto], operation_id="getCustomerBalance"
)
@named
def customer_balance(
    customer_id: uuid.UUID, session: DbSession, ctx: Annotated[RequestContext, Depends(FINANCE_READ)]
) -> list[CustomerBalanceDto]:
    assert ctx.tenant_id is not None
    return ReceivablesService(session, ctx.tenant_id).balances(customer_id)


@router.get(
    "/customers/{customer_id}/statement", response_model=CustomerStatementDto, operation_id="getCustomerStatement"
)
@named
def customer_statement(
    customer_id: uuid.UUID,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(FINANCE_READ)],
    period_from: Annotated[date, Query(alias="from")],
    period_to: Annotated[date, Query(alias="to")],
    currency: Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")] = None,
) -> CustomerStatementDto:
    assert ctx.tenant_id is not None
    return ReceivablesService(session, ctx.tenant_id).statement(customer_id, currency, period_from, period_to)


@router.get("/finance/profitability", response_model=ProfitabilityDto, operation_id="getProfitability")
@named
def profitability(
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(REPORT)],
    group_by: Literal["MACHINE", "CUSTOMER"],
    period_from: Annotated[date, Query(alias="from")],
    period_to: Annotated[date, Query(alias="to")],
) -> ProfitabilityDto:
    assert ctx.tenant_id is not None
    return ProfitabilityService(session, ctx.tenant_id).report(group_by, period_from, period_to)
