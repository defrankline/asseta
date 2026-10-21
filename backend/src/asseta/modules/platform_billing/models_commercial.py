"""Platform commercial model: currencies, negotiated agreements, effective-dated rate versions,
subscriptions, lifecycle history, entitlement policies and events. Platform-owned (RLS: platform/system
write; tenant may read its own rows)."""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, Timestamps, UuidPk, utcnow
from asseta.core.money import RoundingMode
from asseta.modules.platform_billing.enums import (
    AgreementStatus,
    Cadence,
    MidCycleAddPolicy,
    MidCycleRemovePolicy,
    SubscriptionStatus,
)
from asseta.modules.tenancy.models import TenantAccessState


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, native_enum=False, length=24)


class Currency(Base):
    __tablename__ = "currency"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    minor_units: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class CommercialAgreement(UuidPk, Timestamps, Base):
    __tablename__ = "commercial_agreement"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    agreement_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    status: Mapped[AgreementStatus] = mapped_column(_enum(AgreementStatus, "agreement_status"), nullable=False)
    signed_reference: Mapped[str | None] = mapped_column(String(200))
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("payment_terms_days >= 0", name="ck_agreement_terms"),
        CheckConstraint("trial_days >= 0", name="ck_agreement_trial"),
    )


class SubscriptionRateVersion(UuidPk, Base):
    """Immutable once created; a renegotiation is a new version with a later effective_from."""

    __tablename__ = "subscription_rate_version"
    __table_args__ = (
        UniqueConstraint("agreement_id", "version", name="uq_rate_version"),
        UniqueConstraint("agreement_id", "effective_from", name="uq_rate_effective"),
        CheckConstraint("unit_price >= 0", name="ck_rate_price"),
        CheckConstraint("minimum_billable_assets >= 1", name="ck_rate_minimum"),
        CheckConstraint("discount_percent >= 0 AND discount_percent <= 100", name="ck_rate_discount"),
        CheckConstraint("tax_rate_percent >= 0 AND tax_rate_percent <= 100", name="ck_rate_tax"),
    )

    agreement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commercial_agreement.id"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(ForeignKey("currency.code"), nullable=False)
    cadence: Mapped[Cadence] = mapped_column(_enum(Cadence, "cadence"), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    minimum_billable_assets: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    tax_name: Mapped[str | None] = mapped_column(String(40))
    tax_rate_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    mid_cycle_add: Mapped[MidCycleAddPolicy] = mapped_column(_enum(MidCycleAddPolicy, "mid_cycle_add"), nullable=False)
    mid_cycle_remove: Mapped[MidCycleRemovePolicy] = mapped_column(
        _enum(MidCycleRemovePolicy, "mid_cycle_remove"), nullable=False
    )
    rounding_mode: Mapped[RoundingMode] = mapped_column(_enum(RoundingMode, "rounding_mode"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TenantSubscription(UuidPk, Timestamps, Base):
    __tablename__ = "tenant_subscription"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    agreement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commercial_agreement.id"), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(_enum(SubscriptionStatus, "subscription_status"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    billing_start_date: Mapped[date] = mapped_column(Date, nullable=False)  # start + trial
    billing_anchor_day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_effective_date: Mapped[date | None] = mapped_column(Date)
    manually_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # optimistic concurrency
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (CheckConstraint("billing_anchor_day BETWEEN 1 AND 31", name="ck_sub_anchor"),)


class SubscriptionStatusEvent(UuidPk, Base):
    __tablename__ = "subscription_status_event"

    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant_subscription.id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class EntitlementPolicy(UuidPk, Base):
    """Versioned access rules. tenant_id NULL = platform default; tenant row overrides from effective_from."""

    __tablename__ = "entitlement_policy"
    __table_args__ = (
        UniqueConstraint("tenant_id", "version", name="uq_entitlement_policy_version"),
        CheckConstraint("grace_days >= 0", name="ck_policy_grace"),
        CheckConstraint("suspend_after_days >= grace_days", name="ck_policy_suspend"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenant.id"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    grace_days: Mapped[int] = mapped_column(Integer, nullable=False)
    suspend_after_days: Mapped[int] = mapped_column(Integer, nullable=False)
    past_due_access: Mapped[TenantAccessState] = mapped_column(_enum(TenantAccessState, "access_level"), nullable=False)
    suspended_access: Mapped[TenantAccessState] = mapped_column(
        _enum(TenantAccessState, "access_level"), nullable=False
    )
    cancelled_access: Mapped[TenantAccessState] = mapped_column(
        _enum(TenantAccessState, "access_level"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class EntitlementEvent(UuidPk, Base):
    __tablename__ = "entitlement_event"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenant_subscription.id"))
    from_access: Mapped[str] = mapped_column(String(16), nullable=False)
    to_access: Mapped[str] = mapped_column(String(16), nullable=False)
    subscription_status: Mapped[str] = mapped_column(String(24), nullable=False)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entitlement_policy.id"))
    policy_version: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
