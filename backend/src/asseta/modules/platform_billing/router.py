"""Platform-console billing endpoints (PLATFORM scope only)."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.clock import get_today
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, NotFound
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.identity.principal import RequestContext
from asseta.modules.platform_billing import permissions as P
from asseta.modules.platform_billing.allocation import AllocationService
from asseta.modules.platform_billing.dto import (
    ChargePreviewDto,
    CreditAdjustmentIn,
    EndEnrollmentIn,
    EnrollmentDto,
    EnrollmentResultDto,
    EntitlementDto,
    GenerateInvoicesDto,
    GenerateInvoicesIn,
    InvoiceDto,
    NewRateVersionIn,
    OverridePendingChargeIn,
    PaymentDecisionIn,
    PaymentDto,
    PendingChargeDto,
    RateVersionDto,
    RecordPaymentIn,
    SubscriptionDto,
    TransitionIn,
)
from asseta.modules.platform_billing.enrollment_service import EnrollmentService
from asseta.modules.platform_billing.enums import InvoiceKind, InvoiceStatus
from asseta.modules.platform_billing.invoice_service import InvoiceService
from asseta.modules.platform_billing.mappers import invoice_dto, rate_dto
from asseta.modules.platform_billing.models_ledger import PlatformPayment
from asseta.modules.platform_billing.payment_service import PaymentService
from asseta.modules.platform_billing.pending_charge_service import PendingChargeService
from asseta.modules.platform_billing.reporting_service import PlatformDashboardDto, PlatformReportingService
from asseta.modules.platform_billing.repository import BillingRepository, platform_invoice_query
from asseta.modules.platform_billing.subscription_service import SubscriptionService

router = APIRouter(prefix="/api/v1/platform", tags=["platform-billing"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Today = Annotated[date, Depends(get_today)]
IdemKey = Annotated[str | None, Header()]


@router.get("/dashboard", response_model=PlatformDashboardDto, operation_id="getPlatformDashboard")
def dashboard(
    session: DbSession, today: Today, _: Annotated[RequestContext, Depends(P.DASHBOARD_READ)]
) -> PlatformDashboardDto:
    return PlatformReportingService(session).dashboard(today)


@router.get("/tenants/{tenant_id}/subscription", response_model=SubscriptionDto, operation_id="getTenantSubscription")
def tenant_subscription(
    tenant_id: uuid.UUID, session: DbSession, today: Today, ctx: Annotated[RequestContext, Depends(P.SUB_READ)]
) -> SubscriptionDto:
    sub = BillingRepository(session).current_subscription_for_tenant(tenant_id)
    if sub is None:
        raise NotFound("Subscription not found")
    return SubscriptionService(session, ctx.audit_actor()).get(sub, today)


@router.post("/subscriptions/{sid}/transitions", response_model=EntitlementDto, operation_id="transitionSubscription")
def transition(
    sid: uuid.UUID,
    body: TransitionIn,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.SUB_MANAGE)],
) -> EntitlementDto:
    sub = BillingRepository(session).subscription(sid, for_update=True)
    return SubscriptionService(session, ctx.audit_actor()).transition(sub, body, today)


@router.post(
    "/subscriptions/{sid}/entitlement/evaluate", response_model=EntitlementDto, operation_id="evaluateEntitlement"
)
def evaluate(
    sid: uuid.UUID, session: DbSession, today: Today, ctx: Annotated[RequestContext, Depends(P.SUB_MANAGE)]
) -> EntitlementDto:
    sub = BillingRepository(session).subscription(sid, for_update=True)
    return SubscriptionService(session, ctx.audit_actor()).evaluate_entitlement(sub, today)


@router.get("/subscriptions/{sid}/rate-versions", response_model=list[RateVersionDto], operation_id="listRateVersions")
def rate_versions(
    sid: uuid.UUID, session: DbSession, _: Annotated[RequestContext, Depends(P.SUB_READ)]
) -> list[RateVersionDto]:
    repo = BillingRepository(session)
    return [rate_dto(r) for r in repo.rate_versions(repo.subscription(sid).agreement_id)]


@router.post(
    "/subscriptions/{sid}/rate-versions",
    response_model=RateVersionDto,
    status_code=201,
    operation_id="createRateVersion",
)
def create_rate_version(
    sid: uuid.UUID,
    body: NewRateVersionIn,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.PRICING_MANAGE)],
) -> RateVersionDto:
    sub = BillingRepository(session).subscription(sid, for_update=True)
    return SubscriptionService(session, ctx.audit_actor()).add_rate_version(sub, body, today)


@router.get("/subscriptions/{sid}/enrollments", response_model=list[EnrollmentDto], operation_id="listEnrollments")
def enrollments(
    sid: uuid.UUID, session: DbSession, _: Annotated[RequestContext, Depends(P.SUB_READ)], active_on: date | None = None
) -> list[EnrollmentDto]:
    from asseta.modules.platform_billing.models_ledger import SubscriptionAssetEnrollment as E

    if active_on is not None:
        rows = BillingRepository(session).active_enrollments(sid, active_on)
    else:
        rows = list(session.execute(select(E).where(E.subscription_id == sid).order_by(E.asset_label)).scalars())
    return [EnrollmentDto.model_validate(e) for e in rows]


@router.post(
    "/subscriptions/{sid}/enrollments/{eid}/end-preview",
    response_model=ChargePreviewDto | None,
    operation_id="previewEndEnrollment",
)
def preview_end(
    sid: uuid.UUID,
    eid: uuid.UUID,
    body: EndEnrollmentIn,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.ENROLLMENT_MANAGE)],
) -> ChargePreviewDto | None:
    sub = BillingRepository(session).subscription(sid)
    return EnrollmentService(session, ctx.audit_actor()).preview_end(sub, eid, body.effective_to, today)


@router.post(
    "/subscriptions/{sid}/enrollments/{eid}/end", response_model=EnrollmentResultDto, operation_id="endEnrollment"
)
def end_enrollment(
    sid: uuid.UUID,
    eid: uuid.UUID,
    body: EndEnrollmentIn,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.ENROLLMENT_MANAGE)],
) -> EnrollmentResultDto:
    sub = BillingRepository(session).subscription(sid, for_update=True)
    return EnrollmentService(session, ctx.audit_actor()).end(sub, eid, body.effective_to, body.reason, today)


@router.get(
    "/subscriptions/{sid}/pending-charges", response_model=list[PendingChargeDto], operation_id="listPendingCharges"
)
def pending_charges(
    sid: uuid.UUID, session: DbSession, _: Annotated[RequestContext, Depends(P.SUB_READ)]
) -> list[PendingChargeDto]:
    return [PendingChargeDto.model_validate(p) for p in BillingRepository(session).pending_charges(sid)]


@router.patch("/pending-charges/{pid}", response_model=PendingChargeDto, operation_id="overridePendingCharge")
def override_pending(
    pid: uuid.UUID,
    body: OverridePendingChargeIn,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(P.CREDIT_MANAGE)],
) -> PendingChargeDto:
    return PendingChargeService(session, ctx.audit_actor()).override(pid, body)


@router.get(
    "/subscriptions/{sid}/invoices/preview", response_model=InvoiceDto | None, operation_id="previewNextInvoice"
)
def preview_invoice(
    sid: uuid.UUID,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.INVOICE_READ)],
    as_of: date | None = None,
) -> InvoiceDto | None:
    sub = BillingRepository(session).subscription(sid)
    return InvoiceService(session, ctx.audit_actor()).preview_next(sub, as_of or today)


@router.post(
    "/subscriptions/{sid}/invoices/generate", response_model=GenerateInvoicesDto, operation_id="generateInvoices"
)
def generate(
    sid: uuid.UUID,
    body: GenerateInvoicesIn,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.INVOICE_GENERATE)],
) -> GenerateInvoicesDto:
    """Idempotent: existing periods are reported, never re-issued."""
    return InvoiceService(session, ctx.audit_actor()).generate_due(sid, min(body.as_of, today), today)


@router.get("/invoices", response_model=Page[InvoiceDto], operation_id="listPlatformInvoices")
def list_invoices(
    session: DbSession,
    _: Annotated[RequestContext, Depends(P.INVOICE_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    tenant_id: uuid.UUID | None = None,
    status: InvoiceStatus | None = None,
    kind: InvoiceKind | None = None,
) -> Page[InvoiceDto]:
    stmt = platform_invoice_query(tenant_id, status, kind)
    rows, total = paginate(session, stmt, paging)
    return Page(items=[invoice_dto(i, []) for i in rows], total=total, page=paging.page, page_size=paging.page_size)


@router.get("/invoices/{invoice_id}", response_model=InvoiceDto, operation_id="getPlatformInvoice")
def get_invoice(
    invoice_id: uuid.UUID, session: DbSession, today: Today, ctx: Annotated[RequestContext, Depends(P.INVOICE_READ)]
) -> InvoiceDto:
    alloc = AllocationService(session, ctx.audit_actor(), today)
    return alloc.invoice_view(BillingRepository(session).invoice(invoice_id))


@router.get("/payments", response_model=Page[PaymentDto], operation_id="listPlatformPayments")
def list_payments(
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.PAYMENT_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    invoice_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
) -> Page[PaymentDto]:
    stmt = select(PlatformPayment).order_by(PlatformPayment.recorded_at.desc())
    if invoice_id:
        stmt = stmt.where(PlatformPayment.invoice_id == invoice_id)
    if tenant_id:
        stmt = stmt.where(PlatformPayment.tenant_id == tenant_id)
    rows, total = paginate(session, stmt, paging)
    alloc = AllocationService(session, ctx.audit_actor(), today)
    return Page(items=[alloc.payment_dto(p) for p in rows], total=total, page=paging.page, page_size=paging.page_size)


@router.post("/payments", response_model=PaymentDto, status_code=201, operation_id="recordPlatformPayment")
def record_payment(
    body: RecordPaymentIn,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.PAYMENT_MANAGE)],
    idempotency_key: IdemKey = None,
) -> PaymentDto:
    guard = IdempotencyGuard(session, "platform", "recordPlatformPayment", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return PaymentDto.model_validate(replay)
    dto = PaymentService(session, ctx.audit_actor(), today).record(body)
    guard.complete(dto, 201)
    return dto


@router.post("/payments/{payment_id}/decision", response_model=PaymentDto, operation_id="decidePlatformPayment")
def decide_payment(
    payment_id: uuid.UUID,
    body: PaymentDecisionIn,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.PAYMENT_MANAGE)],
) -> PaymentDto:
    dto = PaymentService(session, ctx.audit_actor(), today).decide(payment_id, body)
    sub = BillingRepository(session).current_subscription_for_tenant(dto.tenant_id)
    if sub is not None:  # payment can lift past-due/automatic suspension deterministically
        SubscriptionService(session, ctx.audit_actor()).evaluate_entitlement(sub, today)
    return dto


@router.post("/credit-adjustments", response_model=InvoiceDto, status_code=201, operation_id="applyCredit")
def apply_credit(
    body: CreditAdjustmentIn,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.CREDIT_MANAGE)],
    idempotency_key: IdemKey = None,
) -> InvoiceDto:
    guard = IdempotencyGuard(session, "platform", "applyCredit", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return InvoiceDto.model_validate(replay)
    dto = PaymentService(session, ctx.audit_actor(), today).credit(body)
    guard.complete(dto, 201)
    return dto
