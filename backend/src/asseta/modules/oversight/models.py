"""Site check-ins (DEC-031 M3): a supervisor's GPS check-in at the site at the tenant's scheduled times. Only exists
while the tenant switches OVERSIGHT.site_checkin_required on (person-location data the tenant deliberately asked
for); shown to the person in the app. Append-only (DB guard trigger): a check-in is a record of fact."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, UuidPk, utcnow
from asseta.modules.meter.models import GpsStatus


class SiteCheckin(UuidPk, Base):
    __tablename__ = "site_checkin"
    __table_args__ = (
        UniqueConstraint("tenant_id", "client_id", name="uq_site_checkin_client"),
        Index("ix_site_checkin_staff_time", "tenant_id", "staff_member_id", "captured_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # device id (idempotency)
    staff_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False)
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # device time of check-in
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gps_status: Mapped[GpsStatus] = mapped_column(Enum(GpsStatus, native_enum=False, length=20), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    job_site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job_site.id"), index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("job.id"))  # the person's running job at the site
    distance_m: Mapped[float | None] = mapped_column(Float)  # from the site centre (FIX and a site only)
    source: Mapped[str] = mapped_column(String(8), nullable=False)  # SYNC | API
    device_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
