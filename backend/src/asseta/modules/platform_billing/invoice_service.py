"""Idempotent recurring-invoice generation. One invoice per (subscription, period) enforced by a unique
constraint and a subscription row lock; lines are immutable snapshots (DB trigger)."""

import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import utcnow
from asseta.core.errors import BusinessRuleViolation
from asseta.core.outbox import OutboxWriter
from asseta.modules.platform_billing.calendar import Period, nth_period
from asseta.modules.platform_billing.dto import GenerateInvoicesDto, InvoiceDto, InvoiceLineDto
from asseta.modules.platform_billing.enums import (
    BILLABLE_STATUSES,
    Cadence,
    InvoiceKind,
    InvoiceStatus,
    PendingChargeStatus,
)
from asseta.modules.platform_billing.mappers import invoice_dto, rate_terms
from asseta.modules.platform_billing.models_commercial import TenantSubscription
from asseta.modules.platform_billing.models_ledger import PlatformInvoice, PlatformInvoiceLine
from asseta.modules.platform_billing.pricing import (
    ComputedInvoice,
    EnrolledAsset,
    PendingChargeInput,
    compute_invoice,
)
from asseta.modules.platform_billing.repository import BillingRepository

TOPIC = "asseta.platform.invoice"
MAX_CATCH_UP_PERIODS = 120


class InvoiceService:
    def __init__(self, session: Session, actor: AuditActor):
        self._s = session
        self._repo = BillingRepository(session)
        self._actor = actor
        self._audit = AuditService(session)
        self._outbox = OutboxWriter(session)

    def compute_period(self, sub: TenantSubscription, period: Period) -> tuple[ComputedInvoice, uuid.UUID, str]:
        rate = self._repo.rate_effective(sub.agreement_id, period.start)
        terms = rate_terms(rate, self._repo.currency(rate.currency))
        assets = [
            EnrolledAsset(e.machine_id, e.asset_label) for e in self._repo.active_enrollments(sub.id, period.start)
        ]
        pending = [
            PendingChargeInput(p.id, p.line_type, p.amount, p.explanation, p.service_from, p.service_to)
            for p in self._repo.pending_charges(sub.id, before=period.end)
        ]
        label = "Monthly" if rate.cadence is Cadence.MONTHLY else "Yearly"
        return compute_invoice(terms, period, assets, pending, label), rate.id, rate.currency

    def _due_periods(self, sub: TenantSubscription, as_of: date) -> list[Period]:
        if sub.status not in BILLABLE_STATUSES:
            raise BusinessRuleViolation("Subscription is not in a billable state", code="NOT_BILLABLE")
        cadence = self._repo.rate_effective(sub.agreement_id, sub.billing_start_date).cadence
        periods = []
        for n in range(MAX_CATCH_UP_PERIODS):
            p = nth_period(sub.billing_start_date, sub.billing_anchor_day, cadence, n)
            if p.start > as_of or (sub.cancellation_effective_date and p.start >= sub.cancellation_effective_date):
                break
            periods.append(p)
        return periods

    def preview_next(self, sub: TenantSubscription, as_of: date) -> InvoiceDto | None:
        """Dry run of the next invoice that would be generated (nothing persisted)."""
        for period in self._due_periods(sub, as_of):
            if not self._repo.period_billed(sub.id, period.start):
                computed, _, currency = self.compute_period(sub, period)
                agreement = self._repo.agreement(sub.agreement_id)
                return InvoiceDto(
                    id=None,
                    tenant_id=sub.tenant_id,
                    invoice_number=None,
                    period_start=period.start,
                    period_end=period.end,
                    currency=currency,
                    enrolled_assets=computed.enrolled_assets,
                    billable_assets=computed.billable_assets,
                    subtotal=computed.subtotal,
                    discount_total=computed.discount_total,
                    tax_total=computed.tax_total,
                    total=computed.total,
                    amount_paid=computed.total * 0,
                    credits_applied=computed.total * 0,
                    balance=computed.total,
                    status=None,
                    due_date=as_of + timedelta(days=agreement.payment_terms_days),
                    issued_at=None,
                    lines=[
                        InvoiceLineDto(
                            line_no=i + 1,
                            **{
                                k: getattr(line, k)
                                for k in (
                                    "line_type",
                                    "machine_id",
                                    "description",
                                    "quantity",
                                    "unit_price",
                                    "amount",
                                    "service_from",
                                    "service_to",
                                )
                            },
                        )
                        for i, line in enumerate(computed.lines)
                    ],
                )
        return None

    def generate_due(self, subscription_id: uuid.UUID, as_of: date, today: date) -> GenerateInvoicesDto:
        sub = self._repo.subscription(subscription_id, for_update=True)  # serializes concurrent runs
        agreement = self._repo.agreement(sub.agreement_id)
        created: list[InvoiceDto] = []
        existing: list[date] = []
        for period in self._due_periods(sub, as_of):
            if self._repo.period_billed(sub.id, period.start):
                existing.append(period.start)
                continue
            computed, rate_id, currency = self.compute_period(sub, period)
            number = f"AST-{period.start.year}-{self._repo.next_number('platform_invoice_number_seq'):07d}"
            zero = computed.total * 0
            inv = PlatformInvoice(
                id=uuid.uuid4(),
                tenant_id=sub.tenant_id,
                subscription_id=sub.id,
                rate_version_id=rate_id,
                kind=InvoiceKind.SUBSCRIPTION,
                invoice_number=number,
                period_start=period.start,
                period_end=period.end,
                currency=currency,
                billable_assets=computed.billable_assets,
                enrolled_assets=computed.enrolled_assets,
                subtotal=computed.subtotal,
                discount_total=computed.discount_total,
                tax_total=computed.tax_total,
                total=computed.total,
                amount_paid=zero,
                credits_applied=zero,
                balance=computed.total,
                status=InvoiceStatus.ISSUED if computed.total > 0 else InvoiceStatus.PAID,
                issued_at=utcnow(),
                due_date=today + timedelta(days=agreement.payment_terms_days),
                issued_by=self._actor.user_id,
            )
            self._s.add(inv)
            self._s.flush()
            lines = [
                PlatformInvoiceLine(
                    id=uuid.uuid4(),
                    invoice_id=inv.id,
                    tenant_id=sub.tenant_id,
                    line_no=i + 1,
                    line_type=line.line_type,
                    machine_id=line.machine_id,
                    description=line.description[:300],
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    amount=line.amount,
                    service_from=line.service_from,
                    service_to=line.service_to,
                    pending_charge_id=line.pending_charge_id,
                )
                for i, line in enumerate(computed.lines)
            ]
            self._s.add_all(lines)
            for pending in self._repo.pending_charges(sub.id, before=period.end):
                pending.status, pending.invoice_id = PendingChargeStatus.INVOICED, inv.id
            self._s.flush()
            dto = invoice_dto(inv, lines)
            self._audit.record(
                actor=self._actor,
                action="platform.invoice.issued",
                entity_type="platform_invoice",
                entity_id=inv.id,
                tenant_id=sub.tenant_id,
                after={
                    "invoice_number": number,
                    "total": str(inv.total),
                    "currency": currency,
                    "period_start": period.start.isoformat(),
                },
            )
            self._outbox.emit(
                topic=TOPIC,
                event_type="PlatformInvoiceIssued",
                key=str(sub.tenant_id),
                payload={
                    "invoice_id": str(inv.id),
                    "invoice_number": number,
                    "kind": InvoiceKind.SUBSCRIPTION.value,
                    "total": str(inv.total),
                    "currency": currency,
                    "due_date": inv.due_date.isoformat(),
                },
                tenant_id=sub.tenant_id,
            )
            created.append(dto)
        return GenerateInvoicesDto(created=created, existing_periods=existing)
