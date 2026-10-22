"""DEC-022 platform commerce: product catalog, per-line payment allocations, exactly-once line fulfilment and the
tenant SMS wallet ledger. Platform-owned records; tenants may read their own allocations, fulfilments and wallet."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, Timestamps, UuidPk, utcnow
from asseta.core.lifecycle import Deactivatable
from asseta.modules.platform_billing.enums import (
    FulfilmentStatus,
    InvoiceLineType,
    ProductType,
    SmsWalletEntryType,
)
from asseta.modules.platform_billing.models_ledger import MONEY, _enum


class PlatformProduct(UuidPk, Deactivatable, Timestamps, Base):
    """Something the platform sells. Prices are per currency (decimal strings); SUBSCRIPTION_FEE has no list price:
    it is priced by the tenant's negotiated subscription rate for the billed period."""

    __tablename__ = "platform_product"
    __table_args__ = (
        UniqueConstraint("code", name="uq_platform_product_code"),
        CheckConstraint("product_type <> 'SMS_BUNDLE' OR sms_credits > 0", name="ck_product_sms_credits"),
    )

    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    product_type: Mapped[ProductType] = mapped_column(_enum(ProductType, "product_type"), nullable=False)
    sms_credits: Mapped[int | None] = mapped_column(Integer)  # per unit, SMS_BUNDLE only
    prices: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, default=dict)
    taxable: Mapped[bool] = mapped_column(nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class PlatformLineAllocation(UuidPk, Base):
    """Money applied to an invoice: to a specific line (explicit, platform owner) or, with `line_id` NULL, to the
    invoice as a whole (applied to its lines in line order). Source is a VERIFIED payment or a credit adjustment.
    Released (never deleted) when the invoice is voided; the payment's money then becomes unallocated credit."""

    __tablename__ = "platform_line_allocation"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_platform_allocation_amount"),
        CheckConstraint("num_nonnulls(payment_id, credit_id) = 1", name="ck_platform_allocation_source"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform_invoice.id"), nullable=False, index=True)
    line_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("platform_invoice_line.id"), index=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("platform_payment.id"), index=True)
    credit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_adjustment.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(Text)


class PlatformLineFulfilment(UuidPk, Base):
    """Exactly-once effect of a fully paid line (unique per line). Only FULFILLED -> REVERSED/REVERSAL_FLAGGED."""

    __tablename__ = "platform_line_fulfilment"
    __table_args__ = (UniqueConstraint("line_id", name="uq_platform_fulfilment_line"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform_invoice.id"), nullable=False, index=True)
    line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform_invoice_line.id"), nullable=False)
    line_type: Mapped[InvoiceLineType] = mapped_column(_enum(InvoiceLineType, "invoice_line_type"), nullable=False)
    status: Mapped[FulfilmentStatus] = mapped_column(_enum(FulfilmentStatus, "fulfilment_status"), nullable=False)
    effect: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fulfilled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversal_note: Mapped[str | None] = mapped_column(Text)


class SmsWalletEntry(UuidPk, Base):
    """Append-only SMS credit ledger per tenant. The balance is the sum of `credits`; `balance_after` snapshots it
    (entries are serialized per tenant by an advisory lock). One entry per (type, reference): retries never double."""

    __tablename__ = "sms_wallet_entry"
    __table_args__ = (
        UniqueConstraint("entry_type", "reference_id", name="uq_sms_wallet_entry_reference"),
        CheckConstraint("credits <> 0", name="ck_sms_wallet_entry_credits"),
        CheckConstraint("balance_after >= 0", name="ck_sms_wallet_balance"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    entry_type: Mapped[SmsWalletEntryType] = mapped_column(
        _enum(SmsWalletEntryType, "sms_wallet_entry_type"), nullable=False
    )
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    note: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
