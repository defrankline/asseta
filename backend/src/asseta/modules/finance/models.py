"""Tenant hire finance ledger (R1-G): customer payments with verification, receivable adjustments, supervisor cash
custody and handovers. Strictly separate from the platform subscription ledger (`platform_invoice` & co): no shared
tables, numbering, permissions or endpoints."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from asseta.core.db import Base, SyncRevisioned, UuidPk, utcnow
from asseta.modules.finance.deposit_models import PartialRemittanceApproval, RemittanceEvidence, RemittanceMethod

MONEY = Numeric(18, 4)


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class HirePaymentMethod(StrEnum):
    CASH = "CASH"
    BANK = "BANK"
    MOBILE_MONEY = "MOBILE_MONEY"


class SettlementStatus(StrEnum):
    """Claimed money is evidence of intent only; only VERIFIED settlement reduces balances."""

    CLAIMED = "CLAIMED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class AdjustmentKind(StrEnum):
    # DEC-032 B3/B4 (debits: raise what the customer owes back): a verified payment reversed, a refund paid out.
    PAYMENT_REVERSAL = "PAYMENT_REVERSAL"
    HOURS_REFUND_PAYOUT = "HOURS_REFUND_PAYOUT"
    # A refund returned to the customer's unallocated credit: a record only, no receivable effect.
    HOURS_REFUND_CREDIT = "HOURS_REFUND_CREDIT"


DEBIT_KINDS = frozenset({AdjustmentKind.PAYMENT_REVERSAL, AdjustmentKind.HOURS_REFUND_PAYOUT})


class CustodyEntryType(StrEnum):
    OPENING_BALANCE = "OPENING_BALANCE"  # cash already held when custody tracking starts
    FLOAT_ISSUED = "FLOAT_ISSUED"  # office -> supervisor


class FinancialAdjustment(UuidPk, Base):
    """Append-only correction of what a customer owes (a reversed payment, a refund paid out)."""

    __tablename__ = "financial_adjustment"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_fin_adjustment_amount"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    kind: Mapped[AdjustmentKind] = mapped_column(_enum(AdjustmentKind), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    adjustment_request_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("adjustment_request.id"), index=True)


class CustomerPayment(UuidPk, SyncRevisioned, Base):
    """Money received from a customer (cash collection, bank or mobile money). Unallocated verified money is
    customer credit (deposit/advance)."""

    __tablename__ = "customer_payment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id", name="uq_customer_payment_client"),
        UniqueConstraint("tenant_id", "method", "reference", name="uq_customer_payment_reference"),
        UniqueConstraint("tenant_id", "collection_number", name="uq_customer_payment_number"),
        CheckConstraint("amount > 0", name="ck_customer_payment_amount"),
        CheckConstraint("method = 'CASH' OR reference IS NOT NULL", name="ck_customer_payment_reference"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    method: Mapped[HirePaymentMethod] = mapped_column(_enum(HirePaymentMethod), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_member.id"), index=True)
    status: Mapped[SettlementStatus] = mapped_column(_enum(SettlementStatus), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # API | SYNC
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    # DEC-032 B4: a single stamp when an approved reversal took this payment back (bounced payment, wrong collection).
    # The payment stays as recorded; the balance offsets are separate records. Only these two columns may ever change.
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # DEC-032: the generated reference (COL-<yyyy>-<nnnnn> cash, PAY-... otherwise), distinct from `reference`.
    collection_number: Mapped[str] = mapped_column(String(32), nullable=False)


class SupervisorCashCustody(UuidPk, Base):
    """Append-only custody movements from the office to a supervisor (floats). Collections, cash-paid expenses
    and handovers live in their own tables and are folded into the custody ledger/reconciliation."""

    __tablename__ = "supervisor_cash_custody"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_custody_amount"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    staff_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False, index=True)
    entry_type: Mapped[CustodyEntryType] = mapped_column(_enum(CustodyEntryType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    # Snapshot of the CASH_CUSTODY policy at issue: a float that needs the receiver's acknowledgement counts in
    # custody only once acknowledged (`cash_float_acknowledgement`). Pre-existing entries: counted when issued.
    ack_required: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=text("false"))


class CashHandover(UuidPk, SyncRevisioned, Base):
    """Supervisor -> office cash handover: CLAIMED by the supervisor until an accountant verifies receipt."""

    __tablename__ = "cash_handover"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id", name="uq_cash_handover_client"),
        UniqueConstraint("tenant_id", "remittance_number", name="uq_cash_handover_number"),
        CheckConstraint("amount > 0", name="ck_cash_handover_amount"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    staff_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    handed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SettlementStatus] = mapped_column(_enum(SettlementStatus), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    # Remittance controls (accountability design C). `amount_received` is what the office counted when verifying
    # (null on legacy/rejected rows = the declared amount); set once with the decision. The balance snapshot and the
    # unretained shortfall are fixed at recording: a non-null shortfall is the PARTIAL_REMITTANCE flag.
    amount_received: Mapped[Decimal | None] = mapped_column(MONEY)
    expected_balance: Mapped[Decimal | None] = mapped_column(MONEY)
    partial_shortfall: Mapped[Decimal | None] = mapped_column(MONEY)
    # Stronger remittances (DEC-031 D2): how and where the money went, fixed at recording (null on older rows).
    method: Mapped[RemittanceMethod | None] = mapped_column(_enum(RemittanceMethod))
    deposit_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("company_deposit_account.id"))
    # DEC-032: the generated reference RMT-<yyyy>-<nnnnn>; `reference` stays the bank/mobile transaction reference.
    remittance_number: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[list[RemittanceEvidence]] = relationship(
        RemittanceEvidence,
        primaryjoin="CashHandover.id == foreign(RemittanceEvidence.handover_id)",
        order_by="(RemittanceEvidence.created_at, RemittanceEvidence.id)",
        lazy="selectin",
        viewonly=True,
    )
    partial_approval: Mapped[PartialRemittanceApproval | None] = relationship(
        PartialRemittanceApproval,
        primaryjoin="CashHandover.id == foreign(PartialRemittanceApproval.handover_id)",
        uselist=False,
        lazy="selectin",
        viewonly=True,
    )

    @property
    def evidence_attachment_ids(self) -> list[uuid.UUID]:
        return [e.attachment_id for e in self.evidence]

    @property
    def evidence_status(self) -> str:
        """Guideline 4.5: only what the company confirmed reduces the custodian's balance. DECLARED (a claim), SUPPORTED
        (a claim with supporting evidence), CONFIRMED (independently confirmed as received). A rejected remittance
        keeps the evidence level it had."""
        if self.status is SettlementStatus.VERIFIED:
            return "CONFIRMED"
        return "SUPPORTED" if self.evidence else "DECLARED"

    @property
    def outstanding_difference(self) -> Decimal | None:
        """Declared minus confirmed, once confirmed (guideline 4.5); null until then."""
        if self.status is not SettlementStatus.VERIFIED:
            return None
        received = self.amount_received if self.amount_received is not None else self.amount
        return self.amount - received
