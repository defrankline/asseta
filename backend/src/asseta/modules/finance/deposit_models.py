"""Company deposit accounts (DEC-031 D1): where remitted cash goes (bank account, mobile-money wallet, the cash
office). Tenant data, not configuration: the owner lists the accounts they check against their statements.
Only a masked account number is ever stored. Remittance evidence links (DEC-031 D2) live here too."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, SyncRevisioned, Timestamps, UuidPk, utcnow
from asseta.core.lifecycle import Deactivatable


class DepositAccountType(StrEnum):
    BANK = "BANK"
    MOBILE_MONEY = "MOBILE_MONEY"
    CASH_OFFICE = "CASH_OFFICE"


class RemittanceMethod(StrEnum):
    """How a remittance reached the company. Null on remittances recorded before DEC-031 (cash to the office)."""

    CASH_TO_OFFICE = "CASH_TO_OFFICE"
    BANK_DEPOSIT = "BANK_DEPOSIT"
    MOBILE_MONEY = "MOBILE_MONEY"


# The account type each remittance method deposits into.
METHOD_ACCOUNT_TYPE: dict[RemittanceMethod, DepositAccountType] = {
    RemittanceMethod.CASH_TO_OFFICE: DepositAccountType.CASH_OFFICE,
    RemittanceMethod.BANK_DEPOSIT: DepositAccountType.BANK,
    RemittanceMethod.MOBILE_MONEY: DepositAccountType.MOBILE_MONEY,
}
ACCOUNT_TYPE_METHOD = {v: k for k, v in METHOD_ACCOUNT_TYPE.items()}


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class CompanyDepositAccount(UuidPk, SyncRevisioned, Deactivatable, Timestamps, Base):
    __tablename__ = "company_deposit_account"
    __table_args__ = (
        Index("uq_company_deposit_account_name", "tenant_id", text("lower(name)"), unique=True),
        CheckConstraint("char_length(name) >= 2", name="ck_company_deposit_account_name"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[DepositAccountType] = mapped_column(_enum(DepositAccountType), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(120))  # bank / mobile-money operator
    account_number_masked: Mapped[str | None] = mapped_column(String(40))  # e.g. "•••• 4821"; never the full number
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class RemittanceEvidence(UuidPk, Base):
    """Deposit slip / mobile-money screenshot attached to a remittance (cash handover). Evidence only: it never
    confirms anything; the office still confirms the amount received. Append-only."""

    __tablename__ = "remittance_evidence"
    __table_args__ = (UniqueConstraint("handover_id", "attachment_id", name="uq_remittance_evidence"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    handover_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cash_handover.id"), nullable=False, index=True)
    attachment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("capture_attachment.id"), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
