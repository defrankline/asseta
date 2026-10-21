"""Fleet registry (R1-B): operating areas, categories, machines, staff and effective-dated assignments."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from asseta.core.db import Base, SyncRevisioned, Timestamps, UuidPk, utcnow
from asseta.core.lifecycle import Deactivatable


def _enum(cls: type[StrEnum], length: int = 24) -> Enum:
    return Enum(cls, native_enum=False, length=length)


class MachineStatus(StrEnum):
    ACTIVE = "ACTIVE"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"
    DISPOSED = "DISPOSED"


class Ownership(StrEnum):
    OWNED = "OWNED"
    LEASED = "LEASED"
    HIRED_IN = "HIRED_IN"


class StaffKind(StrEnum):
    SUPERVISOR = "SUPERVISOR"
    OPERATOR = "OPERATOR"
    OTHER = "OTHER"


class AssignmentRole(StrEnum):
    SUPERVISOR = "SUPERVISOR"
    OPERATOR = "OPERATOR"


class OperatingArea(UuidPk, Deactivatable, Timestamps, Base):
    __tablename__ = "operating_area"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_operating_area_code"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class MachineCategory(UuidPk, Deactivatable, Timestamps, Base):
    __tablename__ = "machine_category"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_machine_category_name"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class Machine(UuidPk, SyncRevisioned, Deactivatable, Timestamps, Base):
    __tablename__ = "machine"
    __table_args__ = (
        UniqueConstraint("tenant_id", "asset_code", name="uq_machine_asset_code"),
        CheckConstraint("meter_decimal_places BETWEEN 0 AND 2", name="ck_machine_meter_precision"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    asset_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("machine_category.id"))
    operating_area_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("operating_area.id"))
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    serial_number: Mapped[str | None] = mapped_column(String(100))
    year_of_manufacture: Mapped[int | None] = mapped_column(SmallInteger)
    capacity_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    capacity_unit: Mapped[str | None] = mapped_column(String(20))
    meter_decimal_places: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    ownership: Mapped[Ownership] = mapped_column(_enum(Ownership), nullable=False, default=Ownership.OWNED)
    status: Mapped[MachineStatus] = mapped_column(
        Enum(MachineStatus, name="machine_status", native_enum=False, length=20), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class StaffMember(UuidPk, SyncRevisioned, Deactivatable, Timestamps, Base):
    """Supervisor/operator record; `keycloak_subject` links a login when the person has one."""

    __tablename__ = "staff_member"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_code", name="uq_staff_employee_code"),
        UniqueConstraint("tenant_id", "keycloak_subject", name="uq_staff_subject"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[StaffKind] = mapped_column(_enum(StaffKind), nullable=False)
    employee_code: Mapped[str | None] = mapped_column(String(40))
    phone: Mapped[str | None] = mapped_column(String(40))
    keycloak_subject: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


class MachineAssignment(UuidPk, SyncRevisioned, Base):
    """Effective-dated machine <-> staff assignment; at most one open assignment per (machine, role)."""

    __tablename__ = "machine_assignment"
    __table_args__ = (
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_assignment_dates"),
        Index("uq_assignment_open", "machine_id", "role", unique=True, postgresql_where=text("effective_to IS NULL")),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    staff_member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff_member.id"), nullable=False)
    role: Mapped[AssignmentRole] = mapped_column(_enum(AssignmentRole), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
