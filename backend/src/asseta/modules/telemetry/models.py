"""Telemetry persistence. High-volume tables are RANGE-partitioned by month (partitions managed by migration +
`ensure_telemetry_partitions()`), with GiST spatial and time indexes."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, Timestamps, UuidPk, utcnow
from asseta.modules.tracker.models import TelemetryAdapterKind


class IngestionStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    ACCEPTED_NO_FIX = "ACCEPTED_NO_FIX"  # heartbeat/sensors only; no position stored
    DUPLICATE = "DUPLICATE"
    QUARANTINED = "QUARANTINED"


class QuarantineReason(StrEnum):
    MALFORMED = "MALFORMED"
    UNKNOWN_DEVICE = "UNKNOWN_DEVICE"
    TRACKER_INACTIVE = "TRACKER_INACTIVE"
    UNASSIGNED = "UNASSIGNED"
    NOT_ENROLLED = "NOT_ENROLLED"
    CLOCK_FUTURE = "CLOCK_FUTURE"
    TOO_OLD = "TOO_OLD"


class PositionQuality(StrEnum):
    GOOD = "GOOD"
    LOW_ACCURACY = "LOW_ACCURACY"  # stored as evidence; excluded from geofence/compliance decisions
    IMPLAUSIBLE_JUMP = "IMPLAUSIBLE_JUMP"  # implied speed above policy maximum


class TelemetryGateway(UuidPk, Timestamps, Base):
    """Authenticated ingestion source (e.g. the platform's Traccar). Only a SHA-256 of the key is stored."""

    __tablename__ = "telemetry_gateway"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    adapter: Mapped[TelemetryAdapterKind] = mapped_column(
        Enum(TelemetryAdapterKind, native_enum=False, length=24), nullable=False
    )
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrackerIngestionEvent(Base):
    """Every received message (raw payload retained), its resolution and outcome."""

    __tablename__ = "tracker_ingestion_event"
    __table_args__ = (
        PrimaryKeyConstraint("id", "received_at"),
        Index("ix_ingestion_tracker_time", "tracker_id", "received_at"),
        Index("ix_ingestion_status", "status", "received_at"),
        {"postgresql_partition_by": "RANGE (received_at)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gateway_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    adapter: Mapped[str] = mapped_column(String(24), nullable=False)
    external_device_id: Mapped[str | None] = mapped_column(String(100))
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    tracker_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    machine_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[Any] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[IngestionStatus] = mapped_column(Enum(IngestionStatus, native_enum=False, length=20), nullable=False)
    quarantine_reason: Mapped[QuarantineReason | None] = mapped_column(
        Enum(QuarantineReason, native_enum=False, length=24)
    )
    detail: Mapped[str | None] = mapped_column(Text)


class MachinePositionEvent(Base):
    __tablename__ = "machine_position_event"
    __table_args__ = (
        PrimaryKeyConstraint("id", "event_time"),
        UniqueConstraint("tracker_id", "event_time", name="uq_position_tracker_time"),  # dedupe / replay-safe
        Index("ix_position_machine_time", "machine_id", "event_time"),
        Index("ix_position_location", "location", postgresql_using="gist"),
        {"postgresql_partition_by": "RANGE (event_time)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    machine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tracker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ingestion_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    altitude_m: Mapped[float | None] = mapped_column(Float)
    speed_kmh: Mapped[float | None] = mapped_column(Float)
    heading_deg: Mapped[float | None] = mapped_column(Float)
    satellites: Mapped[int | None] = mapped_column(Integer)
    ignition: Mapped[bool | None] = mapped_column(Boolean)
    motion: Mapped[bool | None] = mapped_column(Boolean)
    engine_hours: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    external_power_v: Mapped[float | None] = mapped_column(Float)
    battery_level_pct: Mapped[float | None] = mapped_column(Float)
    tamper: Mapped[bool | None] = mapped_column(Boolean)
    odometer_km: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    quality: Mapped[PositionQuality] = mapped_column(
        Enum(PositionQuality, native_enum=False, length=20), nullable=False
    )
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False)  # older than machine's latest at receipt
    clock_offset_seconds: Mapped[float] = mapped_column(Float, nullable=False)  # received_at - event_time
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)


class MachineLatestPosition(Base):
    """Newest-by-event-time position per machine (late data never overwrites newer)."""

    __tablename__ = "machine_latest_position"

    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    tracker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    position_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    speed_kmh: Mapped[float | None] = mapped_column(Float)
    heading_deg: Mapped[float | None] = mapped_column(Float)
    ignition: Mapped[bool | None] = mapped_column(Boolean)
    quality: Mapped[str] = mapped_column(String(20), nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # any message
    external_power_v: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class StateDimension(StrEnum):
    ENGINE = "ENGINE"
    MOTION = "MOTION"
    CONNECTIVITY = "CONNECTIVITY"


class MachineStateEvent(UuidPk, Base):
    """Sensor-observed state transitions (event-time ordered; rebuilt idempotently on late data)."""

    __tablename__ = "machine_state_event"
    __table_args__ = (
        UniqueConstraint("machine_id", "dimension", "event_time", name="uq_state_event"),
        Index("ix_state_machine_time", "machine_id", "dimension", "event_time"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    dimension: Mapped[StateDimension] = mapped_column(
        Enum(StateDimension, native_enum=False, length=16), nullable=False
    )
    value: Mapped[str] = mapped_column(String(24), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    position_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    policy_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
