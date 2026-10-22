"""Platform billing queries. Callers run in PLATFORM/SYSTEM scope (or TENANT scope for read-only views);
RLS enforces the boundary underneath."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import ColumnElement, Select, and_, func, or_, select, text
from sqlalchemy.orm import Session

from asseta.core.errors import BusinessRuleViolation, NotFound
from asseta.modules.platform_billing.enums import InvoiceKind, InvoiceLineType, InvoiceStatus, PendingChargeStatus
from asseta.modules.platform_billing.models_catalog import PlatformLineFulfilment
from asseta.modules.platform_billing.models_commercial import (
    CommercialAgreement,
    Currency,
    EntitlementPolicy,
    SubscriptionRateVersion,
    TenantSubscription,
)
from asseta.modules.platform_billing.models_ledger import (
    PlatformInvoice,
    PlatformInvoiceLine,
    SubscriptionAssetEnrollment,
    SubscriptionPendingCharge,
)


def active_on(d: date) -> ColumnElement[bool]:
    e = SubscriptionAssetEnrollment
    return and_(e.effective_from <= d, or_(e.effective_to.is_(None), e.effective_to > d))


def platform_invoice_query(
    tenant_id: uuid.UUID | None = None, status: InvoiceStatus | None = None, kind: InvoiceKind | None = None
) -> Select[PlatformInvoice]:
    """The platform invoice list (latest issued first) shared by the invoices endpoint and the subscription report."""
    stmt = select(PlatformInvoice).order_by(PlatformInvoice.issued_at.desc(), PlatformInvoice.id)
    if tenant_id:
        stmt = stmt.where(PlatformInvoice.tenant_id == tenant_id)
    if kind:
        stmt = stmt.where(PlatformInvoice.kind == kind)
    if status:
        stmt = stmt.where(PlatformInvoice.status == status)
    return stmt


def tenant_invoice_query() -> Select[PlatformInvoice]:
    """The tenant's own platform invoices (RLS), latest period first: the tenant invoice list and report."""
    return select(PlatformInvoice).order_by(
        PlatformInvoice.period_start.desc(), PlatformInvoice.issued_at.desc(), PlatformInvoice.id
    )


class BillingRepository:
    def __init__(self, session: Session):
        self.s = session

    def lock_subscription(self, subscription_id: uuid.UUID) -> None:
        """Serialize all mutations of one subscription (enrollment counts, invoicing) across tenant and platform
        scopes. Advisory lock instead of FOR UPDATE: tenants have no UPDATE policy on tenant_subscription."""
        self.s.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"sub:{subscription_id}"})

    def subscription(self, subscription_id: uuid.UUID, for_update: bool = False) -> TenantSubscription:
        if for_update:
            self.lock_subscription(subscription_id)
        stmt = select(TenantSubscription).where(TenantSubscription.id == subscription_id)
        sub = self.s.execute(stmt.execution_options(populate_existing=True)).scalar_one_or_none()
        if sub is None:
            raise NotFound("Subscription not found")
        return sub

    def current_subscription_for_tenant(self, tenant_id: uuid.UUID) -> TenantSubscription | None:
        return self.s.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .order_by(TenantSubscription.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def agreement(self, agreement_id: uuid.UUID) -> CommercialAgreement:
        agreement = self.s.get(CommercialAgreement, agreement_id)
        if agreement is None:
            raise NotFound("Agreement not found")
        return agreement

    def currency(self, code: str) -> Currency:
        currency = self.s.get(Currency, code)
        if currency is None:
            raise BusinessRuleViolation(f"Currency {code} is not configured", code="CURRENCY_NOT_CONFIGURED")
        return currency

    def rate_versions(self, agreement_id: uuid.UUID) -> list[SubscriptionRateVersion]:
        return list(
            self.s.execute(
                select(SubscriptionRateVersion)
                .where(SubscriptionRateVersion.agreement_id == agreement_id)
                .order_by(SubscriptionRateVersion.version)
            ).scalars()
        )

    def rate_effective(self, agreement_id: uuid.UUID, on: date) -> SubscriptionRateVersion:
        rate = self.s.execute(
            select(SubscriptionRateVersion)
            .where(SubscriptionRateVersion.agreement_id == agreement_id, SubscriptionRateVersion.effective_from <= on)
            .order_by(SubscriptionRateVersion.effective_from.desc())
            .limit(1)
        ).scalar_one_or_none()
        if rate is None:
            raise BusinessRuleViolation(f"No rate version effective on {on}", code="NO_EFFECTIVE_RATE")
        return rate

    def active_enrollments(self, subscription_id: uuid.UUID, on: date) -> list[SubscriptionAssetEnrollment]:
        return list(
            self.s.execute(
                select(SubscriptionAssetEnrollment).where(
                    SubscriptionAssetEnrollment.subscription_id == subscription_id, active_on(on)
                )
            ).scalars()
        )

    def count_active(self, subscription_id: uuid.UUID, on: date, exclude: uuid.UUID | None = None) -> int:
        stmt = select(func.count(func.distinct(SubscriptionAssetEnrollment.machine_id))).where(
            SubscriptionAssetEnrollment.subscription_id == subscription_id, active_on(on)
        )
        if exclude is not None:
            stmt = stmt.where(SubscriptionAssetEnrollment.id != exclude)
        return int(self.s.execute(stmt).scalar_one())

    def open_enrollment_for_machine(self, machine_id: uuid.UUID) -> SubscriptionAssetEnrollment | None:
        return self.s.execute(
            select(SubscriptionAssetEnrollment)
            .where(
                SubscriptionAssetEnrollment.machine_id == machine_id, SubscriptionAssetEnrollment.effective_to.is_(None)
            )
            .with_for_update()
        ).scalar_one_or_none()

    def enrollment(self, enrollment_id: uuid.UUID) -> SubscriptionAssetEnrollment:
        e = self.s.execute(
            select(SubscriptionAssetEnrollment).where(SubscriptionAssetEnrollment.id == enrollment_id).with_for_update()
        ).scalar_one_or_none()
        if e is None:
            raise NotFound("Enrollment not found")
        return e

    def pending_charges(
        self, subscription_id: uuid.UUID, before: date | None = None
    ) -> list[SubscriptionPendingCharge]:
        stmt = select(SubscriptionPendingCharge).where(
            SubscriptionPendingCharge.subscription_id == subscription_id,
            SubscriptionPendingCharge.status == PendingChargeStatus.PENDING,
        )
        if before is not None:
            stmt = stmt.where(SubscriptionPendingCharge.service_from < before)
        return list(self.s.execute(stmt.order_by(SubscriptionPendingCharge.created_at)).scalars())

    def invoice_for_period(self, subscription_id: uuid.UUID, period_start: date) -> PlatformInvoice | None:
        return self.s.execute(
            select(PlatformInvoice).where(
                PlatformInvoice.subscription_id == subscription_id, PlatformInvoice.period_start == period_start
            )
        ).scalar_one_or_none()

    def period_billed(self, subscription_id: uuid.UUID, period_start: date, include_voided: bool = True) -> bool:
        """A period is billed by its scheduled invoice (even when voided: voiding waives it, the scheduler never
        re-issues) or by a non-voided ad-hoc SUBSCRIPTION_FEE line for that period."""
        scheduled = self.invoice_for_period(subscription_id, period_start)
        if scheduled is not None and (include_voided or scheduled.status is not InvoiceStatus.VOIDED):
            return True
        line = self.s.execute(
            select(PlatformInvoiceLine.id)
            .join(PlatformInvoice, PlatformInvoice.id == PlatformInvoiceLine.invoice_id)
            .where(
                PlatformInvoiceLine.subscription_id == subscription_id,
                PlatformInvoiceLine.line_type == InvoiceLineType.SUBSCRIPTION_FEE,
                PlatformInvoiceLine.service_from == period_start,
                PlatformInvoice.status != InvoiceStatus.VOIDED,
            )
            .limit(1)
        ).first()
        return line is not None

    def invoice(self, invoice_id: uuid.UUID, for_update: bool = False) -> PlatformInvoice:
        stmt = select(PlatformInvoice).where(PlatformInvoice.id == invoice_id)
        inv = self.s.execute(stmt.with_for_update() if for_update else stmt).scalar_one_or_none()
        if inv is None:
            raise NotFound("Invoice not found")
        return inv

    def invoice_lines(self, invoice_id: uuid.UUID) -> list[PlatformInvoiceLine]:
        return list(
            self.s.execute(
                select(PlatformInvoiceLine)
                .where(PlatformInvoiceLine.invoice_id == invoice_id)
                .order_by(PlatformInvoiceLine.line_no)
            ).scalars()
        )

    def oldest_overdue_due_date(self, tenant_id: uuid.UUID, as_of: date) -> date | None:
        """Entitlement looks at subscription money only: unpaid scheduled invoices, and ad-hoc invoices whose
        SUBSCRIPTION_FEE line is not yet settled (fulfilled). Unpaid SMS bundles/services never restrict access."""
        scheduled = self.s.execute(
            select(func.min(PlatformInvoice.due_date)).where(
                PlatformInvoice.tenant_id == tenant_id,
                PlatformInvoice.kind == InvoiceKind.SUBSCRIPTION,
                PlatformInvoice.status.not_in([InvoiceStatus.PAID, InvoiceStatus.VOIDED]),
                PlatformInvoice.balance > Decimal(0),
                PlatformInvoice.due_date < as_of,
            )
        ).scalar_one_or_none()
        unsettled = (
            select(PlatformInvoiceLine.id)
            .outerjoin(PlatformLineFulfilment, PlatformLineFulfilment.line_id == PlatformInvoiceLine.id)
            .where(
                PlatformInvoiceLine.invoice_id == PlatformInvoice.id,
                PlatformInvoiceLine.line_type == InvoiceLineType.SUBSCRIPTION_FEE,
                PlatformLineFulfilment.id.is_(None),
            )
            .exists()
        )
        ad_hoc = self.s.execute(
            select(func.min(PlatformInvoice.due_date)).where(
                PlatformInvoice.tenant_id == tenant_id,
                PlatformInvoice.kind == InvoiceKind.AD_HOC,
                PlatformInvoice.status != InvoiceStatus.VOIDED,
                PlatformInvoice.due_date < as_of,
                unsettled,
            )
        ).scalar_one_or_none()
        found = [d for d in (scheduled, ad_hoc) if d is not None]
        return min(found) if found else None

    def entitlement_policy(self, tenant_id: uuid.UUID, on: date) -> EntitlementPolicy:
        policy = self.s.execute(
            select(EntitlementPolicy)
            .where(
                or_(EntitlementPolicy.tenant_id == tenant_id, EntitlementPolicy.tenant_id.is_(None)),
                EntitlementPolicy.effective_from <= on,
            )
            .order_by(
                EntitlementPolicy.tenant_id.is_(None),
                EntitlementPolicy.effective_from.desc(),
                EntitlementPolicy.version.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()
        if policy is None:
            raise BusinessRuleViolation("No entitlement policy configured", code="NO_ENTITLEMENT_POLICY")
        return policy

    def next_number(self, sequence: str) -> int:
        if sequence not in ("platform_invoice_number_seq", "commercial_agreement_number_seq"):
            raise ValueError("unknown sequence")
        return int(self.s.execute(text(f"SELECT nextval('{sequence}')")).scalar_one())
