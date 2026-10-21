import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from asseta.modules.tracker.models import Capability, ProvisioningState, TelemetryAdapterKind

Text100 = Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TrackerModelIn(BaseModel):
    manufacturer: Text100
    model: Text100
    adapter: TelemetryAdapterKind
    protocol: Annotated[str, StringConstraints(min_length=1, max_length=50)]
    declared_capabilities: list[Capability] = Field(min_length=1)
    approved: bool = True
    notes: str | None = Field(default=None, max_length=2000)


class TrackerModelDto(Dto):
    id: uuid.UUID
    manufacturer: str
    model: str
    adapter: TelemetryAdapterKind
    protocol: str
    declared_capabilities: list[Capability]
    approved: bool
    notes: str | None
    version: int = 1
    deactivated_at: datetime | None = None
    deactivation_reason: str | None = None


class TrackerModelUpdateIn(BaseModel):
    """The adapter is fixed once created (registered trackers depend on it). Capability changes apply to trackers
    registered afterwards; existing trackers keep their declared/verified capability rows."""

    manufacturer: Text100
    model: Text100
    protocol: Annotated[str, StringConstraints(min_length=1, max_length=50)]
    declared_capabilities: list[Capability] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=2000)
    version: int = Field(ge=1, description="Optimistic concurrency token from the last read")


class TrackerIn(BaseModel):
    tracker_model_id: uuid.UUID
    external_id: Annotated[str, StringConstraints(min_length=3, max_length=100, strip_whitespace=True)]
    label: Text100
    sim_iccid: str | None = Field(default=None, max_length=32)
    sim_msisdn: str | None = Field(default=None, max_length=32)
    carrier: str | None = Field(default=None, max_length=60)
    credentials_ref: str | None = Field(default=None, max_length=200)


class TrackerUpdateIn(BaseModel):
    """Editable registry details; the device identity (adapter/external_id) and model are fixed."""

    label: Text100
    sim_iccid: str | None = Field(default=None, max_length=32)
    sim_msisdn: str | None = Field(default=None, max_length=32)
    carrier: str | None = Field(default=None, max_length=60)
    credentials_ref: str | None = Field(default=None, max_length=200)
    version: int = Field(ge=1, description="Optimistic concurrency token from the last read")


class CapabilityDto(Dto):
    capability: Capability
    declared: bool
    verified_at: datetime | None
    last_observed_at: datetime | None


class TrackerAssignmentDto(Dto):
    id: uuid.UUID
    tracker_id: uuid.UUID
    machine_id: uuid.UUID
    is_primary: bool
    effective_from: datetime
    effective_to: datetime | None
    reason: str | None


class TrackerDto(Dto):
    id: uuid.UUID
    tracker_model_id: uuid.UUID
    adapter: TelemetryAdapterKind
    external_id: str
    label: str
    sim_iccid: str | None
    sim_msisdn: str | None
    carrier: str | None
    provisioning_state: ProvisioningState
    first_report_at: datetime | None
    last_report_at: datetime | None
    version: int = 1
    capabilities: list[CapabilityDto] = []
    current_assignment: TrackerAssignmentDto | None = None


class AssignTrackerIn(BaseModel):
    machine_id: uuid.UUID
    is_primary: bool = True
    effective_from: datetime
    replace_existing_primary: bool = Field(default=False, description="Swap: end the machine's current primary")
    reason: str | None = Field(default=None, max_length=500)


class UnassignTrackerIn(BaseModel):
    effective_to: datetime
    reason: str = Field(min_length=3, max_length=500)


class TrackerStateIn(BaseModel):
    state: ProvisioningState
    reason: str = Field(min_length=3, max_length=500)
