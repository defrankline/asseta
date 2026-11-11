"""Versioned offline sync protocol DTOs (`/api/v1/sync`, protocol version 1)."""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from asseta.modules.expenses.dto import ExpenseCategoryDto, ExpenseDto, FuelEventDto
from asseta.modules.finance.deposit_accounts import SyncDepositAccountDto
from asseta.modules.finance.dto import CashCustodyBalanceDto, CashHandoverDto, CustomerPaymentDto
from asseta.modules.fleet.dto import MachineDto, StaffDto
from asseta.modules.geospatial.dto import JobSiteDto
from asseta.modules.hours.dto import CustomerDiscountRateDto, HoursPriceDto
from asseta.modules.jobs.dto import AcknowledgementDto, ActivityDto, ContractDto, CustomerDto, JobDto
from asseta.modules.meter.dto import ExceptionDto, MeterCaptureDto, ResetDto
from asseta.modules.pettycash.dto import (
    PettyCashAdvanceDto,
    PettyCashFundDto,
    PettyCashHolderChangeDto,
    PettyCashMovementDto,
    PettyCashWitnessDto,
)
from asseta.modules.platform_billing.dto import Money

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
    # CASH_HANDOVER accepts method, deposit_account_id, evidence_attachment_ids and evidence_upload_ids (purpose
    # REMITTANCE_EVIDENCE); SyncData.deposit_accounts carries the account picker (DEC-031 D2)
    "REMITTANCE_DETAILS_V1",
    # SITE_CHECKIN {client_id, captured_at, gps, job_site_id?}: supervisor GPS check-in at the tenant's times
    # (DEC-031 M3); announced only while the tenant switched site check-ins on (OVERSIGHT.site_checkin_required)
    "OP_SITE_CHECKIN",
    # DAILY_REPORT {id, machine_id, report_date, opening_ref, closing_ref, billable_hours?, unbillable[], note?,
    # evidence_attachment_ids?, evidence_upload_ids? (purpose DAILY_REPORT_EVIDENCE), supersedes_id?, client_created_at}
    "OP_DAILY_REPORT",
    # METER_CAPTURE kind DAILY on a running job accepts changeover_to_customer_id (and changeover_to_job_id)
    "METER_CHANGEOVER",
    "SYNC_CHANGEOVER_JOBS",  # SyncData.changeover_jobs: pending/approved jobs on the supervisor's machines
    "SYNC_UNBILLABLE_REASONS",  # SyncData.unbillable_reasons: tenant list for daily reports (capture permission)
    "SYNC_OPEN_INVOICES",  # SyncData.open_invoices: current open invoices of the recorder's customers (full snapshot)
    # DEC-032 Phase 3: CASH_COLLECTION accepts purchase_id (the purchase's id or offline client id; refused with
    # COLLECTION_LINK_REQUIRED when the tenant requires a link and none is given); CASH_HANDOVER accepts
    # partial_reason + partial_reason_id (PARTIAL_REMITTANCE_REASON_REQUIRED when the balance is not fully remitted);
    # HOURS_TRANSFER_REQUEST accepts
    # evidence_attachment_ids and evidence_upload_ids (purpose ADJUSTMENT_EVIDENCE; EVIDENCE_REQUIRED when required).
    "CASH_DETAILS_V2",
    # DEC-033 petty cash: SyncData.petty_cash_* (the caller's funds with balance and available to spend, money waiting
    # for their acknowledgement, holder changes and advances; full snapshots like cash_custody); EXPENSE accepts
    # paid_from PETTY_CASH + petty_cash_fund_id (+ petty_cash_advance_id); PETTY_CASH_ACKNOWLEDGEMENT,
    # PETTY_CASH_TOP_UP_REQUEST, PETTY_CASH_RETURN, PETTY_CASH_COUNT, PETTY_CASH_ADVANCE_CLEARANCE and
    # PETTY_CASH_HOLDER_CHANGE_ACKNOWLEDGEMENT (evidence_upload_ids: purpose PETTY_CASH_EVIDENCE).
    "OP_PETTY_CASH",
    # SyncData.petty_cash_witnesses: who may witness a count (active, holding tenant.pettycash.count, not the caller),
    # so a witnessed count can be recorded offline; PETTY_CASH_COUNT keeps the count without the witness when the
    # witness lost the permission before the phone synced.
    "SYNC_PETTY_CASH_WITNESSES",
    # SyncData.hours_prices (each synced machine's current hourly rate) and customer_discounts (approved discounts in
    # force today): a phone shows the total of an hours sale as the hours are typed, offline. Total = hours x rate x
    # (100 - discount) / 100, rounded to the currency; the server prices the sale with the same rule when it arrives.
    "SYNC_HOURS_PRICES",
    # PETTY_CASH_ADVANCE: the holder hands out an advance offline (tenant policy advances_enabled); above what the fund
    # has available it is still recorded at sync when the tenant allows overspending offline (the fund shows it).
    "OP_PETTY_CASH_ADVANCE",
    # HOURS_PURCHASE accepts job {planned_start, planned_end?, job_site_id?, contract_id?, note?}: the sale books its
    # prepaid job in the same transaction (needs tenant.job.request; job id = uuid5(op id, "job")); the acked entity
    # carries job {id, job_number, status, ...}. Contract: the one given, else the customer's only active contract (for
    # the site), else a standard walk-in contract when the tenant allows it; else CONFLICT CONTRACT_REQUIRED /
    # CONTRACT_CHOICE_REQUIRED (kept for review: the money changed hands).
    "OP_HOURS_SALE_BOOKING",
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
    "OP_SITE_CHECKIN": "SITE_CHECKIN",
    "OP_DAILY_REPORT": "ENGINE_HOURS",
    "METER_CHANGEOVER": "ENGINE_HOURS",
    "SYNC_CHANGEOVER_JOBS": "ENGINE_HOURS",
    "SYNC_UNBILLABLE_REASONS": "ENGINE_HOURS",
    "OP_PETTY_CASH": "PETTY_CASH",
    "OP_PETTY_CASH_ADVANCE": "PETTY_CASH",
    "SYNC_PETTY_CASH_WITNESSES": "PETTY_CASH",
    "SYNC_HOURS_PRICES": "CUSTOMER_HOURS",
    "OP_HOURS_SALE_BOOKING": "CUSTOMER_HOURS",
}


def announced_capabilities(disabled: frozenset[str]) -> list[str]:
    """The protocol capabilities this tenant's devices may rely on, given its switched-off tenant capabilities."""
    return [c for c in CAPABILITIES if TENANT_CAPABILITY_OF.get(c) not in disabled]


class DeviceRegisterIn(BaseModel):
    device_id: str = Field(min_length=8, max_length=128)
    platform: Literal["ANDROID", "IOS"]
    app_version: str = Field(min_length=1, max_length=32)
    device_model: str | None = Field(default=None, max_length=100, description="e.g. 'Samsung SM-A155' when known")


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


class TenantDeviceDto(DeviceSessionDto):
    """Administration -> Devices: a registered phone, the person it belongs to, and how it was revoked."""

    user_id: uuid.UUID
    user_name: str | None = None
    device_model: str | None
    revoked_by: uuid.UUID | None
    revoked_by_name: str | None = None


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


class SyncChangeoverJobDto(BaseModel):
    """A job a changeover can move on to (DEC-032 A3). A delta may carry a job in another status: drop it from the
    picker unless it is PENDING_APPROVAL or APPROVED. Only PENDING_APPROVAL can be named while another job runs."""

    id: uuid.UUID
    job_number: str
    machine_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str
    status: str
    sync_revision: int


class SyncUnbillableReasonDto(BaseModel):
    """One entry of the tenant's unbillable-reason list for the daily report (DEC-032 A4)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    sync_revision: int


class SyncOpenInvoiceDto(BaseModel):
    """An issued invoice with money still owed, so a collection can be linked to it (DEC-032)."""

    id: uuid.UUID
    invoice_number: str
    customer_id: uuid.UUID
    customer_name: str
    currency: str
    total: Money
    paid: Money
    balance: Money
    due_date: date | None
    issued_at: datetime


class SyncData(BaseModel):
    jobs: list[JobDto] = []
    machines: list[MachineDto] = []
    sites: list[JobSiteDto] = []
    customers: list[CustomerDto] = []
    contracts: list[ContractDto] = []
    staff: list[StaffDto] = []
    expense_categories: list[ExpenseCategoryDto] = []
    cash_custody: list[CashCustodyBalanceDto] = []  # the signed-in supervisor's current custody (server-owned)
    # SYNC_OPEN_INVOICES: open invoices of the customers on the caller's jobs (collection recorders only). A full
    # snapshot on every bootstrap and delta, like cash_custody (invoices carry no sync revision): replace the local set.
    open_invoices: list[SyncOpenInvoiceDto] = []
    # Company deposit accounts for the remittance picker (REMITTANCE_DETAILS_V1; cash recorders only). Bootstrap:
    # active accounts; deltas: changes since the cursor, deactivations included (is_active=false).
    deposit_accounts: list[SyncDepositAccountDto] = []
    # SYNC_CHANGEOVER_JOBS: jobs a changeover can name on the machines the supervisor works on, office-created included.
    # Bootstrap: PENDING_APPROVAL and APPROVED; deltas: changes since the cursor (status says whether it still applies).
    changeover_jobs: list[SyncChangeoverJobDto] = []
    # SYNC_UNBILLABLE_REASONS: bootstrap: active entries; deltas: changes since the cursor, deactivations included.
    unbillable_reasons: list[SyncUnbillableReasonDto] = []
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
    # OP_PETTY_CASH (full snapshots on every bootstrap and delta; replace the local set): the active funds the caller
    # holds with their ledger figures, fundings/top-ups waiting for the caller's acknowledgement, holder changes
    # handing the caller a fund, and advances the caller holds or hands out that are not cleared yet.
    petty_cash_funds: list[PettyCashFundDto] = []
    petty_cash_awaiting: list[PettyCashMovementDto] = []
    petty_cash_holder_changes: list[PettyCashHolderChangeDto] = []
    petty_cash_advances: list[PettyCashAdvanceDto] = []
    # Sent with the funds while the caller holds one and may count (full snapshot; replace the local set).
    petty_cash_witnesses: list[PettyCashWitnessDto] = []
    # SYNC_HOURS_PRICES (full snapshots; replace the local sets): sent to people who sell customer hours.
    hours_prices: list[HoursPriceDto] = []
    customer_discounts: list[CustomerDiscountRateDto] = []


class BootstrapDto(BaseModel):
    protocol_version: int = PROTOCOL_VERSION
    capabilities: list[str] = Field(default_factory=lambda: list(CAPABILITIES))
    server_time: datetime
    tenant_timezone: str = Field(default="UTC", description="IANA zone of the tenant's day boundary (work dates)")
    cursor: int
    device_session: DeviceSessionDto
    data: SyncData
    policy_snapshots: list[PolicySnapshotDto]


class ChangesDto(BaseModel):
    protocol_version: int = PROTOCOL_VERSION
    capabilities: list[str] = Field(default_factory=lambda: list(CAPABILITIES))
    server_time: datetime
    tenant_timezone: str = Field(default="UTC", description="IANA zone of the tenant's day boundary (work dates)")
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
    "SITE_CHECKIN",  # payload SiteCheckinIn {client_id, captured_at, gps, job_site_id?} (OVERSIGHT site check-ins)
    "DAILY_REPORT",  # payload DailyReportIn (op id = report id) + evidence_upload_ids (DEC-032 A4)
    "PETTY_CASH_ACKNOWLEDGEMENT",  # {movement_id, acknowledged, amount_received?, note?} (DEC-033)
    "PETTY_CASH_TOP_UP_REQUEST",  # {fund_id, amount?, note?, above_cap_reason?} (op id = client id)
    "PETTY_CASH_RETURN",  # PettyCashReturnIn (op id = client id) + evidence_upload_ids
    "PETTY_CASH_COUNT",  # PettyCashCountIn (op id = client id) + evidence_upload_ids
    "PETTY_CASH_ADVANCE_CLEARANCE",  # {advance_id, change_returned, note?}
    "PETTY_CASH_HOLDER_CHANGE_ACKNOWLEDGEMENT",  # {holder_change_id, accept, note?}
    "PETTY_CASH_ADVANCE",  # PettyCashAdvanceIn {fund_id, recipient_staff_id, amount, purpose} (op id = client id)
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
    purpose: Literal[
        "METER_PHOTO",
        "SIGNATURE",
        "RESET_EVIDENCE",
        "EXPENSE_RECEIPT",
        "PAYMENT_EVIDENCE",
        "REMITTANCE_EVIDENCE",
        "DAILY_REPORT_EVIDENCE",
        "ADJUSTMENT_EVIDENCE",
        "PETTY_CASH_EVIDENCE",
    ]


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
