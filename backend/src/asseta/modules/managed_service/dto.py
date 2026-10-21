"""Managed-service API DTOs."""

import uuid
from datetime import date, datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from asseta.modules.managed_service.models import MandateScope

Reason = Annotated[str, StringConstraints(min_length=3, max_length=1000, strip_whitespace=True)]
RoleKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{1,63}$")]


class MandateGrantIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: uuid.UUID
    scope: MandateScope
    starts_on: date
    ends_on: date | None = None
    consent_reference: Annotated[str, StringConstraints(min_length=2, max_length=160, strip_whitespace=True)]
    notes: Annotated[str, StringConstraints(max_length=2000, strip_whitespace=True)] = ""

    @model_validator(mode="after")
    def _dates(self) -> Self:
        if self.ends_on is not None and self.ends_on < self.starts_on:
            raise ValueError("ends_on must be on or after starts_on")
        return self


class MandateCloseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1, description="Optimistic concurrency: the version the decision was made on")
    reason: Reason


class MandateAssignmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: uuid.UUID
    role_key: RoleKey


class MandateAssignmentDto(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    display_name: str
    role_key: str
    is_active: bool
    assigned_at: datetime
    removed_at: datetime | None


class MandateDto(BaseModel):
    id: uuid.UUID
    reference: str
    tenant_id: uuid.UUID
    tenant_name: str
    scope: MandateScope
    starts_on: date
    ends_on: date | None
    consent_reference: str
    notes: str
    status: str = Field(description="IN_FORCE | SCHEDULED | EXPIRED | REVOKED | ENDED")
    version: int
    granted_by: str
    granted_at: datetime
    closed_by: str | None
    closed_at: datetime | None
    close_reason: str | None
    active_staff: int


class MandateDetailDto(MandateDto):
    assignments: list[MandateAssignmentDto]


class PlatformStaffDto(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str


class AssignableRoleDto(BaseModel):
    key: str
    permissions: list[str]


class MandateActionDto(BaseModel):
    occurred_at: datetime
    actor: str
    action: str
    entity_type: str
    entity_id: str


class ClientMandateDto(BaseModel):
    """The client's view: the mandate in force (or most recent), who has access and what they did."""

    mandate: MandateDetailDto | None
    recent_actions: list[MandateActionDto]
