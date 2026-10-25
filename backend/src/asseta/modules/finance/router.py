"""Tenant hire invoices, customer payments/allocations, balances, statements and profitability (tenant scope only;
platform scope never reaches these routes or rows)."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.accountability.names import named
from asseta.modules.finance.common import tenant_settings
from asseta.modules.finance.dto import (
    CustomerBalanceDto,
    CustomerPaymentDto,
    CustomerPaymentIn,
    CustomerStatementDto,
    HireAllocateIn,
    HireInvoiceDraftIn,
    HireInvoiceDto,
    HireInvoiceIssueIn,
    HireInvoiceVoidIn,
    ProfitabilityDto,
    SettlementDecisionIn,
)
from asseta.modules.finance.invoice_service import HireInvoiceService, invoice_dto
from asseta.modules.finance.models import CustomerPayment, HireInvoiceStatus, SettlementStatus, TenantHireInvoice
from asseta.modules.finance.payment_service import CustomerPaymentService, payment_dto
from asseta.modules.finance.permissions import FINANCE_READ, INVOICE_WRITE, PAYMENT_WRITE, REPORT, VERIFY
from asseta.modules.finance.profitability import ProfitabilityService
from asseta.modules.finance.receivables import ReceivablesService, overdue_conditions
from asseta.modules.identity.principal import RequestContext

router = APIRouter(prefix="/api/v1/tenant", tags=["finance"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
IdemKey = Annotated[str | None, Header()]


@router.post("/hire-invoices", response_model=HireInvoiceDto, status_code=201, operation_id="createHireInvoiceDraft")
@named
def create_draft(
    body: HireInvoiceDraftIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(INVOICE_WRITE)],
    idempotency_key: IdemKey = None,
) -> HireInvoiceDto:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "createHireInvoiceDraft", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return HireInvoiceDto.model_validate(replay)
    dto = HireInvoiceService(session, ctx, now).create_draft(body)
    guard.complete(dto, 201)
    return dto


@router.get("/hire-invoices", response_model=Page[HireInvoiceDto], operation_id="listHireInvoices")
@named
def list_invoices(
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(FINANCE_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    now: Now,
    status: HireInvoiceStatus | None = None,
    customer_id: uuid.UUID | None = None,
    overdue: Annotated[bool, Query(description="Only issued invoices past due with a balance left")] = False,
) -> Page[HireInvoiceDto]:
    stmt = select(TenantHireInvoice).order_by(TenantHireInvoice.created_at.desc())
    if overdue:
        assert ctx.tenant_id is not None
        tz = ZoneInfo(tenant_settings(session, ctx.tenant_id).timezone)
        stmt = stmt.where(*overdue_conditions(now.astimezone(tz).date()))
    if status:
        stmt = stmt.where(TenantHireInvoice.status == status)
    if customer_id:
        stmt = stmt.where(TenantHireInvoice.customer_id == customer_id)
    if paging.q:
        stmt = stmt.where(TenantHireInvoice.invoice_number.ilike(f"%{paging.q}%"))
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[invoice_dto(session, i) for i in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/hire-invoices/{invoice_id}", response_model=HireInvoiceDto, operation_id="getHireInvoice")
@named
def get_invoice(
    invoice_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(FINANCE_READ)]
) -> HireInvoiceDto:
    return invoice_dto(session, HireInvoiceService(session, ctx, now).invoice(invoice_id))


@router.post("/hire-invoices/{invoice_id}/issue", response_model=HireInvoiceDto, operation_id="issueHireInvoice")
@named
def issue_invoice(
    invoice_id: uuid.UUID,
    body: HireInvoiceIssueIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(INVOICE_WRITE)],
) -> HireInvoiceDto:
    return HireInvoiceService(session, ctx, now).issue(invoice_id, body)


@router.post("/hire-invoices/{invoice_id}/void", response_model=HireInvoiceDto, operation_id="voidHireInvoice")
@named
def void_invoice(
    invoice_id: uuid.UUID,
    body: HireInvoiceVoidIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(INVOICE_WRITE)],
) -> HireInvoiceDto:
    return HireInvoiceService(session, ctx, now).void(invoice_id, body.reason)


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
    _: Annotated[RequestContext, Depends(FINANCE_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    status: SettlementStatus | None = None,
    customer_id: uuid.UUID | None = None,
    staff_member_id: uuid.UUID | None = None,
) -> Page[CustomerPaymentDto]:
    stmt = select(CustomerPayment).order_by(CustomerPayment.received_at.desc())
    if status:
        stmt = stmt.where(CustomerPayment.status == status)
    if customer_id:
        stmt = stmt.where(CustomerPayment.customer_id == customer_id)
    if staff_member_id:
        stmt = stmt.where(CustomerPayment.received_by_staff_id == staff_member_id)
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


@router.post(
    "/customer-payments/{payment_id}/allocations",
    response_model=CustomerPaymentDto,
    operation_id="allocateCustomerPayment",
)
@named
def allocate_payment(
    payment_id: uuid.UUID,
    body: HireAllocateIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(PAYMENT_WRITE)],
    idempotency_key: IdemKey = None,
) -> CustomerPaymentDto:
    guard = IdempotencyGuard(
        session, str(ctx.tenant_id), f"allocateCustomerPayment:{payment_id}", idempotency_key, request_hash(body)
    )
    if (replay := guard.begin()) is not None:
        return CustomerPaymentDto.model_validate(replay)
    dto = CustomerPaymentService(session, ctx, now).allocate(payment_id, body.allocations)
    guard.complete(dto)
    return dto


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
    group_by: Literal["MACHINE", "JOB", "CUSTOMER"],
    period_from: Annotated[date, Query(alias="from")],
    period_to: Annotated[date, Query(alias="to")],
) -> ProfitabilityDto:
    assert ctx.tenant_id is not None
    return ProfitabilityService(session, ctx.tenant_id).report(group_by, period_from, period_to)
