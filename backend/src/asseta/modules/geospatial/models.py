"""PostGIS spatial model (R1-D): job sites, geofences (polygon/corridor), enter/exit events, tracking alerts."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from geoalchemy2 import Geography, Geometry
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, SyncRevisioned, Timestamps, UuidPk, utcnow


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class GeofenceKind(StrEnum):
    ALLOWED_AREA = "ALLOWED_AREA"  # machine should stay inside: alert on exit (beyond tolerance)
    RESTRICTED_AREA = "RESTRICTED_AREA"  # machine must not enter: alert on entry
    SITE_BOUNDARY = "SITE_BOUNDARY"  # informational: time-in-location, proximity


class GeofenceShape(StrEnum):
    POLYGON = "POLYGON"
    CORRIDOR = "CORRIDOR"  # LineString buffered by corridor_width_m


class GeofenceTransition(StrEnum):
    ENTER = "ENTER"
    EXIT = "EXIT"


class AlertType(StrEnum):
    GEOFENCE_EXIT = "GEOFENCE_EXIT"
    RESTRICTED_AREA_ENTRY = "RESTRICTED_AREA_ENTRY"
    UNAUTHORIZED_MOVEMENT = "UNAUTHORIZED_MOVEMENT"
    GPS_ANOMALY = "GPS_ANOMALY"
    TRACKER_STALE = "TRACKER_STALE"
    TRACKER_OFFLINE = "TRACKER_OFFLINE"
    LOW_POWER = "LOW_POWER"
    TAMPER = "TAMPER"


class AlertSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    SUPERSEDED = "SUPERSEDED"  # evidence changed (late/replayed data) — kept for audit, never deleted


class JobSite(UuidPk, SyncRevisioned, Timestamps, Base):
    __tablename__ = "job_site"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_job_site_code"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300))
    center: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Geofence(UuidPk, Timestamps, Base):
    __tablename__ = "geofence"
    __table_args__ = (Index("ix_geofence_area", "area", postgresql_using="gist"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    job_site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job_site.id"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[GeofenceKind] = mapped_column(_enum(GeofenceKind), nullable=False)
    shape: Mapped[GeofenceShape] = mapped_column(_enum(GeofenceShape), nullable=False)
    source_geometry: Mapped[Any] = mapped_column(Geometry(srid=4326, spatial_index=False), nullable=False)
    corridor_width_m: Mapped[float | None] = mapped_column(Float)
    area: Mapped[Any] = mapped_column(Geography(srid=4326, spatial_index=False), nullable=False)  # metre-aware
    applies_to_all_machines: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)


class GeofenceMachine(Base):
    __tablename__ = "geofence_machine"

    geofence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("geofence.id", ondelete="CASCADE"), primary_key=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False)


class GeofenceEvent(UuidPk, Base):
    """Derived enter/exit transitions; rebuilt idempotently from positions when late data arrives."""

    __tablename__ = "geofence_event"
    __table_args__ = (
        UniqueConstraint("machine_id", "geofence_id", "event_time", name="uq_geofence_event"),
        Index("ix_geofence_event_machine_time", "machine_id", "event_time"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    geofence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("geofence.id"), nullable=False)
    transition: Mapped[GeofenceTransition] = mapped_column(_enum(GeofenceTransition), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    position_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)  # metres outside (0 when inside)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TrackingAlert(UuidPk, Base):
    __tablename__ = "tracking_alert"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dedupe_key", name="uq_tracking_alert_dedupe"),
        Index("ix_alert_tenant_status", "tenant_id", "status", "event_time"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    machine_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    tracker_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    alert_type: Mapped[AlertType] = mapped_column(_enum(AlertType), nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(_enum(AlertSeverity), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(_enum(AlertStatus), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    policy_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)
