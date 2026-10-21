"""Customers, rate cards, rental contracts and jobs (R1-E). Prices are owner-approved Decimal terms; jobs move
through explicit authorization states; work logs and acknowledgements are append-only evidence."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, SyncRevisioned, Timestamps, UuidPk, utcnow

MONEY = Numeric(18, 4)
HOURS = Numeric(12, 2)


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class StandbyTreatment(StrEnum):
    EXCLUDED = "EXCLUDED"  # standby/idle not billable
    INCLUDED = "INCLUDED"  # billed as working hours
    STANDBY_RATE = "STANDBY_RATE"  # billed at standby_rate


class ContractStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class JobStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"  # owner-approved price; may start once opening reading exists
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"  # closing reading + acknowledgement captured
    CANCELLED = "CANCELLED"


class ActivityType(StrEnum):
    WORK = "WORK"
    STANDBY = "STANDBY"
    DOWNTIME = "DOWNTIME"
    MOBILIZATION = "MOBILIZATION"
    NOTE = "NOTE"


class Customer(UuidPk, SyncRevisioned, Timestamps, Base):
    __tablename__ = "customer"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_customer_code"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(64))
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class RentalRatePolicy(UuidPk, Base):
    """Tenant rate card, versioned by effective date (default hourly rate per machine category)."""

    __tablename__ = "rental_rate_policy"
    __table_args__ = (
        UniqueConstraint("tenant_id", "machine_category_id", "effective_from", name="uq_rate_card"),
        CheckConstraint("hourly_rate >= 0", name="ck_rate_card_rate"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    machine_category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine_category.id"), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hourly_rate: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    minimum_hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RentalContract(UuidPk, SyncRevisioned, Timestamps, Base):
    __tablename__ = "rental_contract"
    __table_args__ = (UniqueConstraint("tenant_id", "contract_number", name="uq_contract_number"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer.id"), nullable=False, index=True)
    contract_number: Mapped[str] = mapped_column(String(40), nullable=False)
    job_site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job_site.id"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[ContractStatus] = mapped_column(_enum(ContractStatus), nullable=False)
    starts_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reference: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)


class Job(UuidPk, SyncRevisioned, Timestamps, Base):
    """One machine on one contract at one site; billing terms are snapshotted at approval."""

    __tablename__ = "job"
    __table_args__ = (
        UniqueConstraint("tenant_id", "job_number", name="uq_job_number"),
        CheckConstraint("hourly_rate >= 0 AND minimum_hours >= 0 AND mobilization_fee >= 0", name="ck_job_terms"),
        CheckConstraint(
            "discount_percent BETWEEN 0 AND 100 AND tax_rate_percent BETWEEN 0 AND 100", name="ck_job_percentages"
        ),
        Index(
            "uq_job_machine_active",
            "machine_id",
            unique=True,
            postgresql_where=text("status IN ('APPROVED', 'IN_PROGRESS')"),
        ),  # one active job per machine
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    contract_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rental_contract.id"), nullable=False, index=True)
    job_number: Mapped[str] = mapped_column(String(40), nullable=False)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    job_site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job_site.id"))
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_member.id"))
    status: Mapped[JobStatus] = mapped_column(_enum(JobStatus), nullable=False)
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    hourly_rate: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    minimum_hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False)
    standby_treatment: Mapped[StandbyTreatment] = mapped_column(_enum(StandbyTreatment), nullable=False)
    standby_rate: Mapped[Decimal | None] = mapped_column(MONEY)
    mobilization_fee: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    tax_rate_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    rate_source: Mapped[str] = mapped_column(String(64), nullable=False)  # RATE_CARD:<id> | NEGOTIATED
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class JobActivity(UuidPk, Base):
    """Supervisor work log (offline-capable: client_id makes retries idempotent)."""

    __tablename__ = "job_activity"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id", name="uq_job_activity_client"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_activity_times"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    activity_type: Mapped[ActivityType] = mapped_column(_enum(ActivityType), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    billable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    device_id: Mapped[str | None] = mapped_column(String(128))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CustomerAcknowledgement(UuidPk, Base):
    __tablename__ = "customer_acknowledgement"
    __table_args__ = (UniqueConstraint("tenant_id", "client_id", name="uq_ack_client"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    method: Mapped[str] = mapped_column(String(24), nullable=False)  # SIGNATURE | NAME_CONFIRMATION
    signer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    signer_phone: Mapped[str | None] = mapped_column(String(40))
    signature_attachment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    acknowledged_hours: Mapped[Decimal | None] = mapped_column(HOURS)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
