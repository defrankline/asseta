"""Versioned offline sync protocol DTOs (`/api/v1/sync`, protocol version 1)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from asseta.modules.fleet.dto import MachineDto, StaffDto
from asseta.modules.geospatial.dto import JobSiteDto
from asseta.modules.jobs.dto import ContractDto, CustomerDto, JobDto

PROTOCOL_VERSION = 1


class DeviceRegisterIn(BaseModel):
    device_id: str = Field(min_length=8, max_length=128)
    platform: Literal["ANDROID", "IOS"]
    app_version: str = Field(min_length=1, max_length=32)


class DeviceSessionDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: str
    platform: str
    app_version: str
    status: str
    registered_at: datetime
    last_sync_at: datetime | None
    offline_grant_until: datetime
    last_clock_offset_s: float | None
    revoked_at: datetime | None
    revoke_reason: str | None


class PolicySnapshotDto(BaseModel):
    policy_type: str
    scope_key: str  # "tenant" | "machine:<uuid>"
    version_ids: list[uuid.UUID]
    version_stamp: str
    values: dict[str, Any]
    valid_until: datetime


class SyncData(BaseModel):
    jobs: list[JobDto] = []
    machines: list[MachineDto] = []
    sites: list[JobSiteDto] = []
    customers: list[CustomerDto] = []
    contracts: list[ContractDto] = []
    staff: list[StaffDto] = []


class BootstrapDto(BaseModel):
    protocol_version: int = PROTOCOL_VERSION
    server_time: datetime
    cursor: int
    device_session: DeviceSessionDto
    data: SyncData
    policy_snapshots: list[PolicySnapshotDto]


class ChangesDto(BaseModel):
    protocol_version: int = PROTOCOL_VERSION
    server_time: datetime
    cursor: int
    has_more: bool
    data: SyncData
    policy_snapshots: list[PolicySnapshotDto]


OpType = Literal["METER_CAPTURE", "JOB_ACTIVITY", "JOB_ACKNOWLEDGEMENT", "JOB_TRANSITION"]


class OperationIn(BaseModel):
    id: uuid.UUID = Field(description="Device-generated operation id (idempotency key)")
    op_type: OpType
    created_at_device: datetime
    depends_on: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    payload: dict[str, Any]


class PushIn(BaseModel):
    device_now: datetime = Field(description="Device clock at send time (clock offset tracking)")
    operations: list[OperationIn] = Field(min_length=1)


class OperationResultDto(BaseModel):
    id: uuid.UUID
    status: Literal["ACKED", "DUPLICATE", "REJECTED", "CONFLICT", "DEFERRED", "QUARANTINED"]
    result: dict[str, Any] = {}
    error: dict[str, Any] | None = None


class PushResultDto(BaseModel):
    protocol_version: int = PROTOCOL_VERSION
    server_time: datetime
    clock_offset_s: float
    clock_skew_alert: bool
    results: list[OperationResultDto]


class BlobStartIn(BaseModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    purpose: Literal["METER_PHOTO", "SIGNATURE", "RESET_EVIDENCE"]


class BlobSessionDto(BaseModel):
    id: uuid.UUID
    chunk_size: int
    total_chunks: int
    received_chunks: list[int]
    status: str
    attachment_id: uuid.UUID | None
    expires_at: datetime


class RevokeIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
