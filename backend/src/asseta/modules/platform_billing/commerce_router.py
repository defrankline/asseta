"""DEC-022 platform commerce endpoints: product catalog, ad-hoc invoices, void, payment allocation, SMS wallets
(platform console) and the tenant's own SMS wallet."""

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
from asseta.core.lifecycle import IncludeInactive, LifecycleChangeIn
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.identity.principal import RequestContext
from asseta.modules.notification.settings import get_notification_settings
from asseta.modules.platform_billing import permissions as P
from asseta.modules.platform_billing.adhoc_service import AdHocInvoiceService
from asseta.modules.platform_billing.catalog_service import CatalogService, product_dto, product_query
from asseta.modules.platform_billing.dto import InvoiceDto, PaymentDto
from asseta.modules.platform_billing.dto_commerce import (
    AdHocInvoiceIn,
    AllocatePaymentIn,
    ProductDto,
    ProductIn,
    ProductUpdateIn,
    SmsWalletDto,
    SmsWalletEntryDto,
    VoidInvoiceIn,
)
from asseta.modules.platform_billing.enums import ProductType
from asseta.modules.platform_billing.models_catalog import SmsWalletEntry
from asseta.modules.platform_billing.payment_service import PaymentService
from asseta.modules.platform_billing.repository import BillingRepository
from asseta.modules.platform_billing.sms_wallet import SmsWalletService
from asseta.modules.platform_billing.subscription_service import SubscriptionService
from asseta.modules.tenancy.models import Tenant

router = APIRouter(prefix="/api/v1/platform", tags=["platform-commerce"], responses=ERROR_RESPONSES)
tenant_router = APIRouter(prefix="/api/v1/tenant/billing", tags=["tenant-billing"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Today = Annotated[date, Depends(get_today)]
IdemKey = Annotated[str | None, Header()]


# --- catalog -----------------------------------------------------------------------------------------------------
@router.get("/products", response_model=Page[ProductDto], operation_id="listPlatformProducts")
def list_products(
    session: DbSession,
    _: Annotated[RequestContext, Depends(P.CATALOG_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    include_inactive: IncludeInactive = False,
    product_type: ProductType | None = None,
) -> Page[ProductDto]:
    rows, total = paginate(session, product_query(paging.q, include_inactive, product_type), paging)
    return Page(items=[product_dto(p) for p in rows], total=total, page=paging.page, page_size=paging.page_size)


@router.get("/products/{product_id}", response_model=ProductDto, operation_id="getPlatformProduct")
def get_product(
    product_id: uuid.UUID, session: DbSession, ctx: Annotated[RequestContext, Depends(P.CATALOG_READ)]
) -> ProductDto:
    return product_dto(CatalogService(session, ctx.audit_actor()).get(product_id))


@router.post("/products", response_model=ProductDto, status_code=201, operation_id="createPlatformProduct")
def create_product(
    body: ProductIn, session: DbSession, ctx: Annotated[RequestContext, Depends(P.CATALOG_MANAGE)]
) -> ProductDto:
    return CatalogService(session, ctx.audit_actor()).create(body)


@router.put("/products/{product_id}", response_model=ProductDto, operation_id="updatePlatformProduct")
def update_product(
    product_id: uuid.UUID,
    body: ProductUpdateIn,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(P.CATALOG_MANAGE)],
) -> ProductDto:
    return CatalogService(session, ctx.audit_actor()).update(product_id, body)


@router.post("/products/{product_id}/deactivate", response_model=ProductDto, operation_id="deactivatePlatformProduct")
def deactivate_product(
    product_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(P.CATALOG_MANAGE)],
) -> ProductDto:
    return CatalogService(session, ctx.audit_actor()).set_active(product_id, False, body.reason, body.version)


@router.post("/products/{product_id}/reactivate", response_model=ProductDto, operation_id="reactivatePlatformProduct")
def reactivate_product(
    product_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(P.CATALOG_MANAGE)],
) -> ProductDto:
    return CatalogService(session, ctx.audit_actor()).set_active(product_id, True, body.reason, body.version)


# --- ad-hoc invoices, void, allocation ---------------------------------------------------------------------------
@router.post("/invoices/preview", response_model=InvoiceDto, operation_id="previewAdHocInvoice")
def preview_adhoc(
    body: AdHocInvoiceIn, session: DbSession, today: Today, ctx: Annotated[RequestContext, Depends(P.INVOICE_RAISE)]
) -> InvoiceDto:
    """Dry run: nothing is persisted or numbered."""
    return AdHocInvoiceService(session, ctx.audit_actor(), today).preview(body)


@router.post("/invoices", response_model=InvoiceDto, status_code=201, operation_id="raiseAdHocInvoice")
def raise_adhoc(
    body: AdHocInvoiceIn,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.INVOICE_RAISE)],
    idempotency_key: IdemKey = None,
) -> InvoiceDto:
    guard = IdempotencyGuard(session, "platform", "raiseAdHocInvoice", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return InvoiceDto.model_validate(replay)
    dto = AdHocInvoiceService(session, ctx.audit_actor(), today).raise_invoice(body)
    guard.complete(dto, 201)
    return dto


@router.post("/invoices/{invoice_id}/void", response_model=InvoiceDto, operation_id="voidPlatformInvoice")
def void_invoice(
    invoice_id: uuid.UUID,
    body: VoidInvoiceIn,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.INVOICE_VOID)],
) -> InvoiceDto:
    dto = AdHocInvoiceService(session, ctx.audit_actor(), today).void(invoice_id, body.reason)
    _reevaluate(session, ctx, dto.tenant_id, today)
    return dto


@router.post("/payments/{payment_id}/allocations", response_model=PaymentDto, operation_id="allocatePlatformPayment")
def allocate_payment(
    payment_id: uuid.UUID,
    body: AllocatePaymentIn,
    session: DbSession,
    today: Today,
    ctx: Annotated[RequestContext, Depends(P.PAYMENT_MANAGE)],
) -> PaymentDto:
    dto = PaymentService(session, ctx.audit_actor(), today).allocate(payment_id, body.allocations)
    _reevaluate(session, ctx, dto.tenant_id, today)
    return dto


def _reevaluate(session: Session, ctx: RequestContext, tenant_id: uuid.UUID, today: date) -> None:
    sub = BillingRepository(session).current_subscription_for_tenant(tenant_id)
    if sub is not None:
        sub = BillingRepository(session).subscription(sub.id, for_update=True)
        SubscriptionService(session, ctx.audit_actor()).evaluate_entitlement(sub, today)


# --- SMS wallets -------------------------------------------------------------------------------------------------
def _wallet(session: Session, tenant_id: uuid.UUID) -> SmsWalletDto:
    entries = session.execute(
        select(SmsWalletEntry)
        .where(SmsWalletEntry.tenant_id == tenant_id)
        .order_by(SmsWalletEntry.created_at.desc())
        .limit(20)
    ).scalars()
    return SmsWalletDto(
        tenant_id=tenant_id,
        balance=SmsWalletService(session).balance(tenant_id),
        low_balance_threshold=get_notification_settings().sms_wallet_low_threshold,
        recent_entries=[SmsWalletEntryDto.model_validate(e) for e in entries],
    )


def _entries(session: Session, tenant_id: uuid.UUID, paging: PageParams) -> Page[SmsWalletEntryDto]:
    stmt = (
        select(SmsWalletEntry)
        .where(SmsWalletEntry.tenant_id == tenant_id)
        .order_by(SmsWalletEntry.created_at.desc(), SmsWalletEntry.id)
    )
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[SmsWalletEntryDto.model_validate(e) for e in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get("/tenants/{tenant_id}/sms-wallet", response_model=SmsWalletDto, operation_id="getTenantSmsWallet")
def tenant_wallet(
    tenant_id: uuid.UUID, session: DbSession, _: Annotated[RequestContext, Depends(P.SMS_WALLET_READ)]
) -> SmsWalletDto:
    if session.get(Tenant, tenant_id) is None:
        raise NotFound("Tenant not found")
    return _wallet(session, tenant_id)


@router.get(
    "/tenants/{tenant_id}/sms-wallet/entries",
    response_model=Page[SmsWalletEntryDto],
    operation_id="listTenantSmsWalletEntries",
)
def tenant_wallet_entries(
    tenant_id: uuid.UUID,
    session: DbSession,
    _: Annotated[RequestContext, Depends(P.SMS_WALLET_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
) -> Page[SmsWalletEntryDto]:
    return _entries(session, tenant_id, paging)


@tenant_router.get("/sms-wallet", response_model=SmsWalletDto, operation_id="getMySmsWallet")
def my_wallet(session: DbSession, ctx: Annotated[RequestContext, Depends(P.TENANT_BILLING_READ)]) -> SmsWalletDto:
    assert ctx.tenant_id is not None
    return _wallet(session, ctx.tenant_id)


@tenant_router.get("/sms-wallet/entries", response_model=Page[SmsWalletEntryDto], operation_id="listMySmsWalletEntries")
def my_wallet_entries(
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(P.TENANT_BILLING_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
) -> Page[SmsWalletEntryDto]:
    assert ctx.tenant_id is not None
    return _entries(session, ctx.tenant_id, paging)
