"""Tracker registry (R1-C): platform-approved models + capability matrix, tenant trackers, verified
capabilities and effective-dated tracker->machine assignments."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, Timestamps, UuidPk, utcnow
from asseta.core.lifecycle import Deactivatable


class Capability(StrEnum):
    GNSS = "GNSS"
    ACCURACY = "ACCURACY"
    IGNITION = "IGNITION"
    ENGINE_HOURS = "ENGINE_HOURS"
    FUEL_LEVEL = "FUEL_LEVEL"
    EXTERNAL_POWER = "EXTERNAL_POWER"
    BATTERY = "BATTERY"
    TAMPER = "TAMPER"
    MOTION = "MOTION"
    ODOMETER = "ODOMETER"
    OFFLINE_BUFFERING = "OFFLINE_BUFFERING"


class TelemetryAdapterKind(StrEnum):
    TRACCAR = "TRACCAR"


class ProvisioningState(StrEnum):
    REGISTERED = "REGISTERED"  # known to Asseta, not yet reporting
    VERIFIED_REPORTING = "VERIFIED_REPORTING"  # at least one authenticated, assigned, valid report received
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class TrackerModel(UuidPk, Deactivatable, Timestamps, Base):
    """Platform catalog of approved tracker drivers; capabilities are *declared*, never assumed verified."""

    __tablename__ = "tracker_model"
    __table_args__ = (UniqueConstraint("manufacturer", "model", "adapter", name="uq_tracker_model"),)

    manufacturer: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    adapter: Mapped[TelemetryAdapterKind] = mapped_column(_enum(TelemetryAdapterKind), nullable=False)
    protocol: Mapped[str] = mapped_column(String(50), nullable=False)
    declared_capabilities: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)  # False = not offered to tenants
    notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class Tracker(UuidPk, Timestamps, Base):
    __tablename__ = "tracker"
    __table_args__ = (
        # Global (cross-tenant) uniqueness: a device identity can belong to exactly one tenant -> anti-spoofing.
        UniqueConstraint("adapter", "external_id", name="uq_tracker_external_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    tracker_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracker_model.id"), nullable=False)
    adapter: Mapped[TelemetryAdapterKind] = mapped_column(_enum(TelemetryAdapterKind), nullable=False)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    sim_iccid: Mapped[str | None] = mapped_column(String(32))
    sim_msisdn: Mapped[str | None] = mapped_column(String(32))
    carrier: Mapped[str | None] = mapped_column(String(60))
    credentials_ref: Mapped[str | None] = mapped_column(String(200))  # reference into a secret store, never a secret
    provisioning_state: Mapped[ProvisioningState] = mapped_column(_enum(ProvisioningState), nullable=False)
    first_report_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_report_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Bumped only by user edits (not by ingestion touching last_report_at), so edits never race telemetry.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class TrackerCapability(Base):
    __tablename__ = "tracker_capability"

    tracker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracker.id", ondelete="CASCADE"), primary_key=True)
    capability: Mapped[Capability] = mapped_column(_enum(Capability, 32), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    declared: Mapped[bool] = mapped_column(Boolean, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # first observed in real data
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrackerAssignment(UuidPk, Base):
    __tablename__ = "tracker_assignment"
    __table_args__ = (
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_tracker_assignment_dates"),
        Index(
            "uq_tracker_assignment_open_tracker",
            "tracker_id",
            unique=True,
            postgresql_where=text("effective_to IS NULL"),
        ),
        Index(
            "uq_tracker_assignment_open_primary",
            "machine_id",
            unique=True,
            postgresql_where=text("effective_to IS NULL AND is_primary"),
        ),
        Index("ix_tracker_assignment_lookup", "tracker_id", "effective_from"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    tracker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tracker.id"), nullable=False)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
