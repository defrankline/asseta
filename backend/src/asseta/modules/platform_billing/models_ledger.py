"""Platform subscription ledger: billable-asset enrollments, pending mid-cycle charges, immutable invoices,
payments and credit adjustments. Strictly separate from tenant equipment-hire finance (S-003)."""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow
from asseta.modules.platform_billing.enums import (
    EnrollmentEndReason,
    InvoiceKind,
    InvoiceLineType,
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
    PendingChargeStatus,
)

MONEY = Numeric(18, 4)


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, native_enum=False, length=24)


class SubscriptionAssetEnrollment(UuidPk, Base):
    """A machine's billable membership interval [effective_from, effective_to). Tracker swaps never touch it."""

    __tablename__ = "subscription_asset_enrollment"
    __table_args__ = (
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_enrollment_dates"),
        # A machine can be open-enrolled only once: prevents double billing from duplicates/retries.
        Index("uq_enrollment_open_machine", "machine_id", unique=True, postgresql_where=text("effective_to IS NULL")),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant_subscription.id"), nullable=False, index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False)
    asset_label: Mapped[str] = mapped_column(String(64), nullable=False)  # commercial snapshot for platform
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    end_reason: Mapped[EnrollmentEndReason | None] = mapped_column(_enum(EnrollmentEndReason, "enrollment_end"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    ended_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class SubscriptionPendingCharge(UuidPk, Base):
    """Mid-cycle proration computed at change time under the stored policy; reviewable/overridable (audited)
    until included in an invoice, then frozen."""

    __tablename__ = "subscription_pending_charge"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant_subscription.id"), nullable=False)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscription_asset_enrollment.id"), nullable=False)
    rate_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscription_rate_version.id"), nullable=False)
    line_type: Mapped[InvoiceLineType] = mapped_column(_enum(InvoiceLineType, "invoice_line_type"), nullable=False)
    service_from: Mapped[date] = mapped_column(Date, nullable=False)
    service_to: Mapped[date] = mapped_column(Date, nullable=False)
    days: Mapped[int] = mapped_column(nullable=False)
    period_days: Mapped[int] = mapped_column(nullable=False)
    computed_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    override_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[PendingChargeStatus] = mapped_column(
        _enum(PendingChargeStatus, "pending_charge_status"), nullable=False
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("platform_invoice.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class PlatformInvoice(UuidPk, Base):
    __tablename__ = "platform_invoice"
    __table_args__ = (
        # Idempotent issuance: exactly one recurring invoice per subscription period.
        UniqueConstraint("subscription_id", "period_start", name="uq_invoice_subscription_period"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    # Ad-hoc invoices have no subscription/rate of their own (a SUBSCRIPTION_FEE line carries its subscription).
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenant_subscription.id"))
    rate_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subscription_rate_version.id"))
    kind: Mapped[InvoiceKind] = mapped_column(
        _enum(InvoiceKind, "invoice_kind"),
        nullable=False,
        default=InvoiceKind.SUBSCRIPTION,
        server_default=InvoiceKind.SUBSCRIPTION.value,
    )
    invoice_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)  # exclusive (ad-hoc: lines' service span)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    billable_assets: Mapped[int] = mapped_column(nullable=False)
    enrolled_assets: Mapped[int] = mapped_column(nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    credits_applied: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(_enum(InvoiceStatus, "invoice_status"), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    void_reason: Mapped[str | None] = mapped_column(Text)


class PlatformInvoiceLine(UuidPk, Base):
    """Immutable after insert (DB trigger rejects UPDATE/DELETE)."""

    __tablename__ = "platform_invoice_line"

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform_invoice.id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False)
    line_type: Mapped[InvoiceLineType] = mapped_column(_enum(InvoiceLineType, "invoice_line_type"), nullable=False)
    machine_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    service_from: Mapped[date | None] = mapped_column(Date)
    service_to: Mapped[date | None] = mapped_column(Date)
    pending_charge_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subscription_pending_charge.id"))
    # Ad-hoc catalog lines (DEC-022): what fulfilment does once the line is fully paid.
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("platform_product.id"))
    sms_credits: Mapped[int | None] = mapped_column()  # SMS_BUNDLE: credits added to the tenant SMS wallet
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenant_subscription.id"))


class PlatformPayment(UuidPk, Base):
    __tablename__ = "platform_payment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "method", "reference", name="uq_platform_payment_reference"),
        CheckConstraint("amount > 0", name="ck_platform_payment_amount"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    # Invoice the payment was recorded against; NULL = tenant-level payment applied to the oldest open invoices.
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("platform_invoice.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    # Explicit per-line allocation requested by the platform owner, applied on verification.
    allocation_plan: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB)
    method: Mapped[PaymentMethod] = mapped_column(_enum(PaymentMethod, "payment_method"), nullable=False)
    reference: Mapped[str] = mapped_column(String(120), nullable=False)
    received_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(_enum(PaymentStatus, "payment_status"), nullable=False)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class CreditAdjustment(UuidPk, Base):
    __tablename__ = "credit_adjustment"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_credit_amount"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform_invoice.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


# Catalog/allocation/fulfilment/wallet tables reference the ledger (and lines reference products): register together.
from asseta.modules.platform_billing import models_catalog  # noqa: E402, F401
