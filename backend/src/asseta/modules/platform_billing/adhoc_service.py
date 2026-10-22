"""Ad-hoc platform invoices (DEC-022): the platform owner raises an invoice at any time with mixed catalog lines.
Same numbering sequence and immutability as scheduled invoices (lines insert-only, snapshot guarded by trigger);
corrections only by void (reversal). A SUBSCRIPTION_FEE line reuses the scheduled subscription pricing for its period
(`InvoiceService.compute_period`) and marks the period billed, so the scheduler never bills it twice."""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import utcnow
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.money import RoundingMode, quantize
from asseta.core.outbox import OutboxWriter
from asseta.modules.platform_billing.allocation import AllocationService
from asseta.modules.platform_billing.calendar import Period, period_containing
from asseta.modules.platform_billing.catalog_service import CatalogService
from asseta.modules.platform_billing.dto import InvoiceDto
from asseta.modules.platform_billing.dto_commerce import AdHocInvoiceIn, AdHocLineIn
from asseta.modules.platform_billing.enums import (
    BILLABLE_STATUSES,
    InvoiceKind,
    InvoiceLineType,
    InvoiceStatus,
    PendingChargeStatus,
    ProductType,
)
from asseta.modules.platform_billing.fulfilment import FulfilmentService
from asseta.modules.platform_billing.invoice_service import InvoiceService
from asseta.modules.platform_billing.mappers import invoice_dto
from asseta.modules.platform_billing.models_catalog import PlatformProduct
from asseta.modules.platform_billing.models_commercial import SubscriptionRateVersion, TenantSubscription
from asseta.modules.platform_billing.models_ledger import PlatformInvoice, PlatformInvoiceLine
from asseta.modules.platform_billing.repository import BillingRepository
from asseta.modules.tenancy.models import Tenant, TenantSettings

TOPIC = "asseta.platform.invoice"
HUNDRED = Decimal(100)
ZERO = Decimal(0)


@dataclass
class Draft:
    lines: list[PlatformInvoiceLine]
    subtotal: Decimal = ZERO
    discount_total: Decimal = ZERO
    tax_total: Decimal = ZERO
    enrolled: int = 0
    billable: int = 0
    rate_id: uuid.UUID | None = None
    pending_subscription: TenantSubscription | None = None
    pending_period: Period | None = None


class AdHocInvoiceService:
    def __init__(self, session: Session, actor: AuditActor, today: date):
        self._s, self._actor, self._today = session, actor, today
        self._repo = BillingRepository(session)
        self._audit = AuditService(session)

    def _sub_and_rate(self, tenant_id: uuid.UUID) -> tuple[TenantSubscription | None, SubscriptionRateVersion | None]:
        sub = self._repo.current_subscription_for_tenant(tenant_id)
        if sub is None:
            return None, None
        try:
            return sub, self._repo.rate_effective(sub.agreement_id, max(self._today, sub.billing_start_date))
        except BusinessRuleViolation:
            return sub, None

    def _subscription_line(
        self, d: Draft, sub: TenantSubscription | None, item: AdHocLineIn, currency: str, tenant_id: uuid.UUID
    ) -> PlatformInvoiceLine:
        if sub is None:
            raise BusinessRuleViolation("Tenant has no subscription", code="NO_SUBSCRIPTION")
        if item.period_start is None:
            raise BusinessRuleViolation("Subscription lines need period_start", code="PERIOD_REQUIRED")
        if item.unit_price is not None or item.discount_percent or item.quantity != 1:
            raise BusinessRuleViolation(
                "Subscription fees are priced by the negotiated rate", code="SUBSCRIPTION_PRICE_FROM_RATE"
            )
        if sub.status not in BILLABLE_STATUSES:
            raise BusinessRuleViolation("Subscription is not in a billable state", code="NOT_BILLABLE")
        if d.pending_subscription is not None:
            raise BusinessRuleViolation("One subscription period per invoice", code="DUPLICATE_PERIOD_LINE")
        self._repo.lock_subscription(sub.id)  # serializes with the scheduler's generate_due
        start = item.period_start
        cadence = self._repo.rate_effective(sub.agreement_id, sub.billing_start_date).cadence
        if start < sub.billing_start_date:
            raise BusinessRuleViolation("Period precedes billing start", code="INVALID_PERIOD")
        period = period_containing(sub.billing_start_date, sub.billing_anchor_day, cadence, start)
        if period.start != start:
            raise BusinessRuleViolation(f"Billing periods start on {period.start}", code="INVALID_PERIOD")
        if sub.cancellation_effective_date and start >= sub.cancellation_effective_date:
            raise BusinessRuleViolation("Period is after the cancellation date", code="INVALID_PERIOD")
        if self._repo.period_billed(sub.id, start, include_voided=False):
            raise Conflict(f"Period starting {start} is already invoiced", code="PERIOD_ALREADY_BILLED")
        computed, rate_id, rate_currency = InvoiceService(self._s, self._actor).compute_period(sub, period)
        if rate_currency != currency:
            raise BusinessRuleViolation("Subscription rate is in another currency", code="CURRENCY_MISMATCH")
        d.subtotal += computed.subtotal
        d.discount_total += computed.discount_total
        d.tax_total += computed.tax_total
        d.enrolled, d.billable, d.rate_id = computed.enrolled_assets, computed.billable_assets, rate_id
        d.pending_subscription, d.pending_period = sub, period
        label = item.description or (
            f"Subscription {period.start} to {period.end - timedelta(days=1)}: {computed.billable_assets} billable "
            f"asset(s) (incl. discount/tax per agreement)"
        )
        return self._line(
            tenant_id,
            InvoiceLineType.SUBSCRIPTION_FEE,
            label,
            Decimal(1),
            computed.total,
            computed.total,
            service=(period.start, period.end),
            subscription_id=sub.id,
        )

    def _line(
        self,
        tenant_id: uuid.UUID,
        line_type: InvoiceLineType,
        description: str,
        quantity: Decimal,
        unit_price: Decimal,
        amount: Decimal,
        product: PlatformProduct | None = None,
        sms_credits: int | None = None,
        service: tuple[date, date] | None = None,
        subscription_id: uuid.UUID | None = None,
    ) -> PlatformInvoiceLine:
        return PlatformInvoiceLine(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            line_type=line_type,
            description=description[:300],
            quantity=quantity,
            unit_price=unit_price,
            amount=amount,
            service_from=service[0] if service else None,
            service_to=service[1] if service else None,
            product_id=product.id if product else None,
            sms_credits=sms_credits,
            subscription_id=subscription_id,
        )

    def _draft(self, body: AdHocInvoiceIn) -> tuple[Draft, str, date, Tenant]:
        tenant = self._s.get(Tenant, body.tenant_id)
        if tenant is None:
            raise NotFound("Tenant not found")
        sub, rate = self._sub_and_rate(tenant.id)
        settings = self._s.get(TenantSettings, tenant.id)
        currency = body.currency or (rate.currency if rate else settings.currency if settings else "TZS")
        minor = self._repo.currency(currency).minor_units
        rounding = rate.rounding_mode if rate else RoundingMode.HALF_UP
        catalog = CatalogService(self._s, self._actor)
        d, taxable = Draft([]), ZERO
        for item in body.lines:
            product = catalog.get(item.product_id)
            if not product.is_active:
                raise BusinessRuleViolation(f"Product {product.code} is inactive", code="PRODUCT_INACTIVE")
            if product.product_type is ProductType.SUBSCRIPTION_FEE:
                line = self._subscription_line(d, sub, item, currency, tenant.id)
                line.product_id = product.id
                d.lines.append(line)
                continue
            if item.period_start is not None:
                raise BusinessRuleViolation("period_start applies to subscription lines", code="PERIOD_NOT_ALLOWED")
            unit = item.unit_price if item.unit_price is not None else product.prices.get(currency)
            if unit is None:
                raise BusinessRuleViolation(
                    f"Product {product.code} has no {currency} price; give a negotiated unit_price", code="NO_PRICE"
                )
            unit = quantize(Decimal(unit), minor, rounding)
            gross = quantize(item.quantity * unit, minor, rounding)
            discount = quantize(gross * item.discount_percent / HUNDRED, minor, rounding)
            credits = None
            if product.product_type is ProductType.SMS_BUNDLE:
                if item.quantity != item.quantity.to_integral_value():
                    raise BusinessRuleViolation("SMS bundles are sold in whole units", code="WHOLE_UNITS_REQUIRED")
                credits = int(item.quantity) * int(product.sms_credits or 0)
            text = item.description or product.name
            if credits:
                text += f" ({credits:,} SMS credits)"
            if discount:
                text += f" — discount {item.discount_percent.normalize()}%"
            line_type = InvoiceLineType(product.product_type.value)
            d.lines.append(
                self._line(tenant.id, line_type, text, item.quantity, unit, gross - discount, product, credits)
            )
            d.subtotal += gross
            d.discount_total += discount
            taxable += (gross - discount) if product.taxable else ZERO
        if rate is not None and rate.tax_rate_percent and taxable > 0:
            tax = quantize(taxable * rate.tax_rate_percent / HUNDRED, minor, rounding)
            if tax:
                d.lines.append(
                    self._line(
                        tenant.id,
                        InvoiceLineType.TAX,
                        f"{rate.tax_name or 'Tax'} {rate.tax_rate_percent.normalize()}%",
                        Decimal(1),
                        tax,
                        tax,
                    )
                )
                d.tax_total += tax
        agreement = self._repo.agreement(sub.agreement_id) if sub else None
        due = body.due_date or self._today + timedelta(days=agreement.payment_terms_days if agreement else 14)
        if due < self._today:
            raise BusinessRuleViolation("Due date cannot be in the past", code="DUE_DATE_PAST")
        return d, currency, due, tenant

    def _invoice(self, body: AdHocInvoiceIn, d: Draft, currency: str, due: date, number: str | None) -> PlatformInvoice:
        spans = [(x.service_from, x.service_to) for x in d.lines if x.service_from and x.service_to]
        total = sum((x.amount for x in d.lines), ZERO)
        return PlatformInvoice(
            id=uuid.uuid4(),
            tenant_id=body.tenant_id,
            subscription_id=None,
            rate_version_id=d.rate_id,
            kind=InvoiceKind.AD_HOC,
            invoice_number=number or "",
            period_start=min((s for s, _ in spans), default=self._today),
            period_end=max((e for _, e in spans), default=self._today),
            currency=currency,
            billable_assets=d.billable,
            enrolled_assets=d.enrolled,
            subtotal=d.subtotal,
            discount_total=d.discount_total,
            tax_total=d.tax_total,
            total=total,
            amount_paid=ZERO,
            credits_applied=ZERO,
            balance=total,
            status=InvoiceStatus.ISSUED if total > 0 else InvoiceStatus.PAID,
            issued_at=utcnow(),
            due_date=due,
            issued_by=self._actor.user_id,
            notes=body.notes,
        )

    def preview(self, body: AdHocInvoiceIn) -> InvoiceDto:
        d, currency, due, _ = self._draft(body)
        inv = self._invoice(body, d, currency, due, None)
        for i, line in enumerate(d.lines):
            line.line_no, line.invoice_id = i + 1, inv.id
        dto = invoice_dto(inv, d.lines)
        dto.id, dto.invoice_number, dto.status, dto.issued_at = None, None, None, None
        for line_dto in dto.lines:
            line_dto.id = None
        return dto

    def raise_invoice(self, body: AdHocInvoiceIn) -> InvoiceDto:
        d, currency, due, tenant = self._draft(body)
        number = f"AST-{self._today.year}-{self._repo.next_number('platform_invoice_number_seq'):07d}"
        inv = self._invoice(body, d, currency, due, number)
        self._s.add(inv)
        self._s.flush()
        for i, line in enumerate(d.lines):
            line.line_no, line.invoice_id = i + 1, inv.id
        self._s.add_all(d.lines)
        if d.pending_subscription is not None and d.pending_period is not None:
            for pending in self._repo.pending_charges(d.pending_subscription.id, before=d.pending_period.end):
                pending.status, pending.invoice_id = PendingChargeStatus.INVOICED, inv.id
        self._s.flush()
        summary = {
            "invoice_number": number,
            "kind": "AD_HOC",
            "total": str(inv.total),
            "currency": currency,
            "lines": [f"{x.line_type.value}:{x.amount}" for x in d.lines],
        }
        self._audit.record(
            actor=self._actor,
            action="platform.invoice.issued",
            entity_type="platform_invoice",
            entity_id=inv.id,
            tenant_id=tenant.id,
            after=summary,
            reason=body.notes,
        )
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="PlatformInvoiceIssued",
            key=str(tenant.id),
            payload={
                "invoice_id": str(inv.id),
                "invoice_number": number,
                "kind": "AD_HOC",
                "total": str(inv.total),
                "currency": currency,
                "due_date": due.isoformat(),
            },
            tenant_id=tenant.id,
        )
        return AllocationService(self._s, self._actor, self._today).invoice_view(inv)

    def void(self, invoice_id: uuid.UUID, reason: str) -> InvoiceDto:
        """Reversal, never deletion: allocations are released (the money becomes the tenant's unallocated credit),
        fulfilled lines are reversed where possible, the snapshot stays."""
        inv = self._repo.invoice(invoice_id, for_update=True)
        if inv.status is InvoiceStatus.VOIDED:
            raise Conflict("Invoice already voided", code="INVOICE_ALREADY_VOIDED")
        alloc = AllocationService(self._s, self._actor, self._today)
        released = alloc.release_invoice(inv, f"Invoice voided: {reason}")
        before = {"status": inv.status.value, "balance": str(inv.balance), "amount_paid": str(inv.amount_paid)}
        inv.status, inv.voided_at, inv.voided_by, inv.void_reason = (
            InvoiceStatus.VOIDED,
            utcnow(),
            self._actor.user_id,
            reason,
        )
        inv.amount_paid = inv.credits_applied = inv.balance = ZERO
        self._s.flush()
        reversed_ = FulfilmentService(self._s, self._actor, self._today).reverse_for_void(inv, reason)
        self._audit.record(
            actor=self._actor,
            action="platform.invoice.voided",
            entity_type="platform_invoice",
            entity_id=inv.id,
            tenant_id=inv.tenant_id,
            before=before,
            after={
                "status": "VOIDED",
                "released_payments": str(released),
                "fulfilments": {str(r.line_id): r.status.value for r in reversed_},
            },
            reason=reason,
        )
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="PlatformInvoiceVoided",
            key=str(inv.tenant_id),
            payload={
                "invoice_id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "reason": reason,
                "released_payments": str(released),
            },
            tenant_id=inv.tenant_id,
        )
        return alloc.invoice_view(inv)
