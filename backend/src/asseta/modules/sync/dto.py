"""Versioned offline sync protocol DTOs (`/api/v1/sync`, protocol version 1)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from asseta.modules.expenses.dto import ExpenseCategoryDto, ExpenseDto, FuelEventDto
from asseta.modules.finance.dto import CashCustodyBalanceDto, CashHandoverDto, CustomerPaymentDto
from asseta.modules.fleet.dto import MachineDto, StaffDto
from asseta.modules.geospatial.dto import JobSiteDto
from asseta.modules.jobs.dto import AcknowledgementDto, ActivityDto, ContractDto, CustomerDto, JobDto
from asseta.modules.meter.dto import ExceptionDto, MeterCaptureDto, ResetDto

PROTOCOL_VERSION = 1
# Additive, optional features of protocol 1 (old clients ignore unknown fields; new clients check before relying).
CAPABILITIES = [
    "SUPERVISOR_INBOX_V1",
    "OP_METER_RESET_REQUEST",
    "OP_JOB_REQUEST",
    "OP_CASH_TRANSFER",  # CASH_TRANSFER, CASH_TRANSFER_ACKNOWLEDGEMENT, CASH_FLOAT_ACKNOWLEDGEMENT
    "OP_HOURS_PURCHASE",  # walk-in/registered customer hours purchase (+ payment claim and evidence uploads)
    "OP_HOURS_TRANSFER_REQUEST",
    "METER_DAILY_READING",  # METER_CAPTURE accepts kind DAILY (job_id optional, machine_id instead)
    "OP_METER_BASELINE",
    "OP_METER_CORRECTION",
    "OP_CASH_RETENTION_REQUEST",  # CASH_RETENTION_REQUEST (ask to keep field cash; approved by another person)
]
# Protocol capabilities that belong to a tenant capability (`asseta.modules.policy.capabilities`): not announced
# while the tenant has it switched off, and their operations are then refused (CONFLICT, the capability's code).
TENANT_CAPABILITY_OF = {
    "OP_HOURS_PURCHASE": "CUSTOMER_HOURS",
    "OP_HOURS_TRANSFER_REQUEST": "CUSTOMER_HOURS",
    "METER_DAILY_READING": "ENGINE_HOURS",
    "OP_METER_BASELINE": "ENGINE_HOURS",
    "OP_METER_CORRECTION": "ENGINE_HOURS",
    "OP_CASH_TRANSFER": "CASH_CUSTODY",
    "OP_CASH_RETENTION_REQUEST": "CASH_CUSTODY",
}


def announced_capabilities(disabled: frozenset[str]) -> list[str]:
    """The protocol capabilities this tenant's devices may rely on, given its switched-off tenant capabilities."""
    return [c for c in CAPABILITIES if TENANT_CAPABILITY_OF.get(c) not in disabled]


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


class SyncMeterCaptureDto(MeterCaptureDto):
    """The caller's reading with the server's findings and their review state. `sync_revision` is the highest
    revision of the capture and its findings, so a reviewer's decision re-delivers the capture."""

    sync_revision: int
    review_status: Literal["NONE", "PENDING_REVIEW", "REVIEWED"] = "NONE"
    findings: list[ExceptionDto] = Field(default_factory=list)


class SyncJobActivityDto(ActivityDto):
    job_id: uuid.UUID
    duration_minutes: int | None = Field(default=None, description="ended_at - started_at; null while open")
    recorded_by: uuid.UUID | None
    received_at: datetime
    sync_revision: int


class SyncAcknowledgementDto(AcknowledgementDto):
    job_id: uuid.UUID
    client_id: uuid.UUID
    recorded_by: uuid.UUID | None
    received_at: datetime
    sync_revision: int


class SyncExpenseDto(ExpenseDto):
    sync_revision: int


class SyncFuelEventDto(FuelEventDto):
    sync_revision: int


class SyncCashCollectionDto(CustomerPaymentDto):
    sync_revision: int


class SyncCashHandoverDto(CashHandoverDto):
    sync_revision: int


class SyncMeterResetDto(ResetDto):
    decided_by: uuid.UUID | None
    created_at: datetime
    sync_revision: int


class SyncData(BaseModel):
    jobs: list[JobDto] = []
    machines: list[MachineDto] = []
    sites: list[JobSiteDto] = []
    customers: list[CustomerDto] = []
    contracts: list[ContractDto] = []
    staff: list[StaffDto] = []
    expense_categories: list[ExpenseCategoryDto] = []
    cash_custody: list[CashCustodyBalanceDto] = []  # the signed-in supervisor's current custody (server-owned)
    # Supervisor inbox (SUPERVISOR_INBOX_V1): the caller's own field records, upsert by (id, sync_revision).
    # Bootstrap: last 30 days + everything still open; deltas: anything changed since the cursor.
    my_meter_captures: list[SyncMeterCaptureDto] = []
    my_meter_resets: list[SyncMeterResetDto] = []
    my_job_activities: list[SyncJobActivityDto] = []
    my_acknowledgements: list[SyncAcknowledgementDto] = []
    my_expenses: list[SyncExpenseDto] = []
    my_fuel_events: list[SyncFuelEventDto] = []
    my_cash_collections: list[SyncCashCollectionDto] = []
    my_cash_handovers: list[SyncCashHandoverDto] = []


class BootstrapDto(BaseModel):
    protocol_version: int = PROTOCOL_VERSION
    capabilities: list[str] = Field(default_factory=lambda: list(CAPABILITIES))
    server_time: datetime
    cursor: int
    device_session: DeviceSessionDto
    data: SyncData
    policy_snapshots: list[PolicySnapshotDto]


class ChangesDto(BaseModel):
    protocol_version: int = PROTOCOL_VERSION
    capabilities: list[str] = Field(default_factory=lambda: list(CAPABILITIES))
    server_time: datetime
    cursor: int
    has_more: bool
    data: SyncData
    policy_snapshots: list[PolicySnapshotDto]


OpType = Literal[
    "METER_CAPTURE",
    "JOB_ACTIVITY",
    "JOB_ACKNOWLEDGEMENT",
    "JOB_TRANSITION",
    "EXPENSE",
    "CASH_COLLECTION",
    "CASH_HANDOVER",
    "CASH_TRANSFER",  # field-to-field cash transfer (payload CashTransferIn, client_id required)
    "CASH_TRANSFER_ACKNOWLEDGEMENT",  # {transfer_id, acknowledged, amount_received?, note?}
    "CASH_FLOAT_ACKNOWLEDGEMENT",  # {entry_id, acknowledged, amount_received?, note?}
    "FUEL_EVENT",
    "METER_RESET_REQUEST",
    "JOB_REQUEST",
    "HOURS_PURCHASE",  # customer hours purchase recorded in the field (payment stays CLAIMED until verified)
    "HOURS_TRANSFER_REQUEST",  # request to move remaining hours to another machine (approved per tenant policy)
    "METER_BASELINE",  # baseline proposal (engine-hour accountability)
    "METER_CORRECTION",  # reading correction proposal (approved by a second person)
    "CASH_RETENTION_REQUEST",  # payload CashRetentionIn, client_id required (tenant policy cash.retention_allowed)
]


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
    purpose: Literal["METER_PHOTO", "SIGNATURE", "RESET_EVIDENCE", "EXPENSE_RECEIPT", "PAYMENT_EVIDENCE"]


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
