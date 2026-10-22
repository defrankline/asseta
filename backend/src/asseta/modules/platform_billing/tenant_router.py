"""Tenant-scope billing views and billable-asset enrollment (tenant sees only its own data via RLS)."""

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
from asseta.modules.identity.principal import RequestContext
from asseta.modules.platform_billing import permissions as P
from asseta.modules.platform_billing.allocation import AllocationService
from asseta.modules.platform_billing.dto import (
    ChargePreviewDto,
    EndEnrollmentIn,
    EnrollAssetIn,
    EnrollmentResultDto,
    InvoiceDto,
    SubscriptionDto,
)
from asseta.modules.platform_billing.enrollment_service import EnrollmentService
from asseta.modules.platform_billing.models_commercial import TenantSubscription
from asseta.modules.platform_billing.models_ledger import PlatformInvoice
from asseta.modules.platform_billing.repository import BillingRepository
from asseta.modules.platform_billing.subscription_service import SubscriptionService

router = APIRouter(prefix="/api/v1/tenant/billing", tags=["tenant-billing"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Today = Annotated[date, Depends(get_today)]


def _subscription(session: Session, ctx: RequestContext, lock: bool = False) -> TenantSubscription:
    assert ctx.tenant_id is not None
    sub = BillingRepository(session).current_subscription_for_tenant(ctx.tenant_id)
    if sub is None:
        raise NotFound("Subscription not found")
    return BillingRepository(session).subscription(sub.id, for_update=True) if lock else sub


@router.get("/subscription", response_model=SubscriptionDto, operation_id="getMySubscription")
def my_subscription(
    session: DbSession, today: Today, ctx: Annotated[RequestContext, Depends(P.TENANT_BILLING_READ)]
) -> SubscriptionDto:
    return SubscriptionService(session, ctx.audit_actor()).get(_subscription(session, ctx), today)


@router.get("/invoices", response_model=list[InvoiceDto], operation_id="listMyPlatformInvoices")
def my_invoices(
    session: DbSession, today: Today, ctx: Annotated[RequestContext, Depends(P.TENANT_BILLING_READ)]
) -> list[InvoiceDto]:
    alloc = AllocationService(session, ctx.audit_actor(), today)
    rows = session.execute(
        select(PlatformInvoice).order_by(PlatformInvoice.period_start.desc(), PlatformInvoice.issued_at.desc())
    ).scalars()
    return [alloc.invoice_view(i) for i in rows]


@router.post("/enrollments/preview", response_model=ChargePreviewDto | None, operation_id="previewEnrollment")
def preview(
    body: EnrollAssetIn,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.TENANT_BILLING_ENROLL)],
) -> ChargePreviewDto | None:
    sub = _subscription(session, ctx)
    return EnrollmentService(session, ctx.audit_actor()).preview_add(sub, body.machine_id, body.effective_from, today)


@router.post("/enrollments", response_model=EnrollmentResultDto, status_code=201, operation_id="enrollMachine")
def enroll(
    body: EnrollAssetIn,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.TENANT_BILLING_ENROLL)],
    idempotency_key: Annotated[str | None, Header()] = None,
) -> EnrollmentResultDto:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "enrollMachine", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return EnrollmentResultDto.model_validate(replay)
    sub = _subscription(session, ctx, lock=True)
    dto = EnrollmentService(session, ctx.audit_actor()).enroll(sub, body.machine_id, body.effective_from, today)
    guard.complete(dto, 201)
    return dto


@router.post("/enrollments/{eid}/end", response_model=EnrollmentResultDto, operation_id="unenrollMachine")
def end(
    eid: uuid.UUID,
    body: EndEnrollmentIn,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.TENANT_BILLING_ENROLL)],
) -> EnrollmentResultDto:
    sub = _subscription(session, ctx, lock=True)
    return EnrollmentService(session, ctx.audit_actor()).end(sub, eid, body.effective_to, body.reason, today)
