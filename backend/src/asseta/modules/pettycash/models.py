"""Petty cash funds (DEC-033): a named pot of company cash with one accountable holder, an approved limit and its own
ledger. Balances are never stored: they are derived from the movement rows below (see `ledger`).

Every table is tenant-owned (FORCE RLS). Evidence rows are append-only (counts) or guarded by triggers so that only
the recorded workflow steps can change a row (movements, holder changes, adjustments, advances)."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, Timestamps, UuidPk, utcnow
from asseta.core.lifecycle import Deactivatable
from asseta.modules.finance.custody_models import AcknowledgementMethod, CashDecisionStatus
from asseta.modules.finance.models import MONEY


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


def _evidence() -> Mapped[list[uuid.UUID]]:
    return mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)


class MovementKind(StrEnum):
    FUNDING = "FUNDING"  # first money into a fund
    TOP_UP = "TOP_UP"  # imprest refill: approved spending since the last top-up, never above the limit
    RETURN = "RETURN"  # money handed back from the fund to the office


class MovementStatus(StrEnum):
    PROPOSED = "PROPOSED"  # FUNDING / TOP_UP: waiting for an approver
    APPROVED = "APPROVED"  # approved, not yet handed over
    REJECTED = "REJECTED"
    ISSUED = "ISSUED"  # handed over; waiting for the holder's acknowledgement (not in the balance yet)
    ACKNOWLEDGED = "ACKNOWLEDGED"  # the holder confirmed the amount received (that amount is in the balance)
    DISPUTED = "DISPUTED"  # the holder did not receive it (nothing in the balance; a variance is opened)
    CLAIMED = "CLAIMED"  # RETURN: the holder says it was handed back (never reduces the balance yet)
    CONFIRMED = "CONFIRMED"  # RETURN: the office counted what it received (that amount leaves the balance)


INBOUND = (MovementKind.FUNDING, MovementKind.TOP_UP)


class CountReason(StrEnum):
    ROUTINE = "ROUTINE"
    HOLDER_CHANGE = "HOLDER_CHANGE"


class HolderChangeStatus(StrEnum):
    PENDING = "PENDING"  # the old holder stays accountable until the new holder acknowledges
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"


class AdvanceStatus(StrEnum):
    OUTSTANDING = "OUTSTANDING"
    CLEARED = "CLEARED"


class PettyCashFund(UuidPk, Deactivatable, Timestamps, Base):
    __tablename__ = "petty_cash_fund"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_petty_cash_fund_code"),
        CheckConstraint("approved_limit > 0", name="ck_petty_cash_fund_limit"),
        CheckConstraint("low_balance_level IS NULL OR low_balance_level >= 0", name="ck_petty_cash_fund_low"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    holder_staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False, index=True)
    job_site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job_site.id"))
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    approved_limit: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    low_balance_level: Mapped[Decimal | None] = mapped_column(MONEY)
    note: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class PettyCashMovement(UuidPk, Base):
    """Money into (FUNDING, TOP_UP) or out of (RETURN) a fund. Never a cost: transfers, not spending."""

    __tablename__ = "petty_cash_movement"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_petty_cash_movement_number"),
        UniqueConstraint("tenant_id", "client_id", name="uq_petty_cash_movement_client"),
        CheckConstraint("amount > 0", name="ck_petty_cash_movement_amount"),
        CheckConstraint("amount_received IS NULL OR amount_received >= 0", name="ck_petty_cash_movement_received"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    fund_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("petty_cash_fund.id"), nullable=False, index=True)
    kind: Mapped[MovementKind] = mapped_column(_enum(MovementKind), nullable=False)
    number: Mapped[str] = mapped_column(String(32), nullable=False)  # PC-<yyyy>-<nnnnn>
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    holder_staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    status: Mapped[MovementStatus] = mapped_column(_enum(MovementStatus), nullable=False)
    deposit_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("company_deposit_account.id"))
    method: Mapped[str | None] = mapped_column(String(24))
    reference: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    suggested_amount: Mapped[Decimal | None] = mapped_column(MONEY)  # TOP_UP: the pre-filled imprest amount
    cap_amount: Mapped[Decimal | None] = mapped_column(MONEY)  # limit - balance when proposed
    above_cap_reason: Mapped[str | None] = mapped_column(Text)
    basis_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # spending counted since
    evidence_attachment_ids: Mapped[list[uuid.UUID]] = _evidence()
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # API | SYNC
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    client_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # acknowledged / confirmed by
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    amount_received: Mapped[Decimal | None] = mapped_column(MONEY)
    receipt_method: Mapped[AcknowledgementMethod | None] = mapped_column(_enum(AcknowledgementMethod))
    receipt_note: Mapped[str | None] = mapped_column(Text)
    receipt_client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class PettyCashCount(UuidPk, Base):
    """A physical count against the expected cash at that moment (snapshot). Append-only evidence."""

    __tablename__ = "petty_cash_count"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_petty_cash_count_number"),
        UniqueConstraint("tenant_id", "client_id", name="uq_petty_cash_count_client"),
        CheckConstraint("counted_amount >= 0", name="ck_petty_cash_count_amount"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    fund_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("petty_cash_fund.id"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reason: Mapped[CountReason] = mapped_column(_enum(CountReason), nullable=False)
    holder_staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    counted_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    expected_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    difference: Mapped[Decimal] = mapped_column(MONEY, nullable=False)  # counted - expected
    counted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    counted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    witness_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    self_count: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evidence_attachment_ids: Mapped[list[uuid.UUID]] = _evidence()
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    policy_version: Mapped[str | None] = mapped_column(String(80))
    client_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PettyCashHolderChange(UuidPk, Base):
    """A fund handed from one holder to another, with a count at the change. Until the new holder acknowledges, the
    old holder stays accountable (the fund's holder does not change)."""

    __tablename__ = "petty_cash_holder_change"
    __table_args__ = (CheckConstraint("from_staff_id <> to_staff_id", name="ck_petty_cash_holder_change_parties"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    fund_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("petty_cash_fund.id"), nullable=False, index=True)
    from_staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False)
    to_staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False, index=True)
    count_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("petty_cash_count.id"), nullable=False)
    status: Mapped[HolderChangeStatus] = mapped_column(_enum(HolderChangeStatus), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class PettyCashAdjustment(UuidPk, Base):
    """Authorised correction of a fund's balance (signed). Proposed by one person, approved by another (never the
    holder); counts only once APPROVED."""

    __tablename__ = "petty_cash_adjustment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_petty_cash_adjustment_number"),
        CheckConstraint("amount <> 0", name="ck_petty_cash_adjustment_amount"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    fund_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("petty_cash_fund.id"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    reason_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cash_reason.id"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_attachment_ids: Mapped[list[uuid.UUID]] = _evidence()
    status: Mapped[CashDecisionStatus] = mapped_column(_enum(CashDecisionStatus), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class PettyCashAdvance(UuidPk, Base):
    """Phase 3: cash handed from a fund to a person before a purchase. Spent through expenses linked to the advance and
    cleared with the change returned (the difference opens a variance)."""

    __tablename__ = "petty_cash_advance"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_petty_cash_advance_number"),
        UniqueConstraint("tenant_id", "client_id", name="uq_petty_cash_advance_client"),
        CheckConstraint("amount > 0", name="ck_petty_cash_advance_amount"),
        CheckConstraint("change_returned IS NULL OR change_returned >= 0", name="ck_petty_cash_advance_change"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    fund_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("petty_cash_fund.id"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recipient_staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AdvanceStatus] = mapped_column(_enum(AdvanceStatus), nullable=False)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    client_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleared_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    spent_amount: Mapped[Decimal | None] = mapped_column(MONEY)  # approved linked expenses when cleared
    change_returned: Mapped[Decimal | None] = mapped_column(MONEY)
    clear_note: Mapped[str | None] = mapped_column(Text)
    clear_client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
