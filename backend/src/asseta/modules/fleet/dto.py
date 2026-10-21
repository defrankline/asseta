import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from asseta.modules.fleet.models import AssignmentRole, MachineStatus, Ownership, StaffKind

Code = Annotated[str, StringConstraints(min_length=1, max_length=64, strip_whitespace=True)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LifecycleDto(Dto):
    """Soft-lifecycle state shown on details pages (deactivated records are hidden from lists by default)."""

    is_active: bool
    deactivated_at: datetime | None
    deactivation_reason: str | None
    version: int


Version = Annotated[int, Field(ge=1, description="Optimistic concurrency token from the last read")]


class MachineFields(BaseModel):
    name: Name
    category_id: uuid.UUID | None = None
    operating_area_id: uuid.UUID | None = None
    manufacturer: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    serial_number: str | None = Field(default=None, max_length=100)
    year_of_manufacture: int | None = Field(default=None, ge=1950, le=2100)
    capacity_value: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    capacity_unit: str | None = Field(default=None, max_length=20)
    meter_decimal_places: int = Field(default=1, ge=0, le=2)
    ownership: Ownership = Ownership.OWNED


class MachineCreateIn(MachineFields):
    asset_code: Code


class MachineUpdateIn(MachineFields):
    status: MachineStatus
    version: int = Field(ge=1, description="Optimistic concurrency token from the last read")


class MachineDto(Dto):
    id: uuid.UUID
    asset_code: str
    name: str
    category_id: uuid.UUID | None
    operating_area_id: uuid.UUID | None
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    year_of_manufacture: int | None
    capacity_value: Decimal | None
    capacity_unit: str | None
    meter_decimal_places: int
    ownership: Ownership
    status: MachineStatus
    version: int
    created_at: datetime
    deactivated_at: datetime | None = None
    deactivation_reason: str | None = None


class CategoryIn(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]
    description: str | None = Field(default=None, max_length=300)


class CategoryUpdateIn(CategoryIn):
    version: Version


class CategoryDto(LifecycleDto):
    id: uuid.UUID
    name: str
    description: str | None


class AreaIn(BaseModel):
    code: Annotated[str, StringConstraints(min_length=1, max_length=32, strip_whitespace=True)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]


class AreaUpdateIn(AreaIn):
    version: Version


class AreaDto(LifecycleDto):
    id: uuid.UUID
    code: str
    name: str


class StaffIn(BaseModel):
    full_name: Name
    kind: StaffKind
    employee_code: str | None = Field(default=None, max_length=40)
    phone: str | None = Field(default=None, max_length=40)
    keycloak_subject: str | None = Field(default=None, max_length=64)
    is_active: bool = True


class StaffUpdateIn(BaseModel):
    full_name: Name
    kind: StaffKind
    employee_code: str | None = Field(default=None, max_length=40)
    phone: str | None = Field(default=None, max_length=40)
    keycloak_subject: str | None = Field(
        default=None, max_length=64, description="Login link; changing it moves field-app access to another login"
    )
    version: Version


class StaffDto(LifecycleDto):
    id: uuid.UUID
    full_name: str
    kind: StaffKind
    employee_code: str | None
    phone: str | None
    keycloak_subject: str | None


class AssignIn(BaseModel):
    staff_member_id: uuid.UUID
    role: AssignmentRole
    effective_from: datetime


class EndAssignmentIn(BaseModel):
    effective_to: datetime


class AssignmentDto(Dto):
    id: uuid.UUID
    machine_id: uuid.UUID
    staff_member_id: uuid.UUID
    role: AssignmentRole
    effective_from: datetime
    effective_to: datetime | None
