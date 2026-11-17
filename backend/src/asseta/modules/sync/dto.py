"""Versioned offline sync protocol DTOs (`/api/v1/sync`, protocol version 1)."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema

from asseta.modules.customers.dto import CustomerDto
from asseta.modules.expenses.dto import ExpenseCategoryDto, ExpenseDto, FuelEventDto
from asseta.modules.finance.deposit_accounts import SyncDepositAccountDto
from asseta.modules.finance.dto import CashCustodyBalanceDto, CashHandoverDto, CustomerPaymentDto
from asseta.modules.fleet.dto import MachineDto, StaffDto
from asseta.modules.geospatial.dto import JobSiteDto
from asseta.modules.hours.dto import CreditInvoiceDto, CustomerDiscountRateDto, HoursPriceDto
from asseta.modules.machine_reports.dto import (
    AvailableHoursDto,
    MachineReportDto,
    MachineReportReasonDto,
    MachineReportStatusDto,
)
from asseta.modules.meter.dto import ExceptionDto, MeterCaptureDto, ResetDto
from asseta.modules.pettycash.dto import (
    PettyCashAdvanceDto,
    PettyCashFundDto,
    PettyCashHolderChangeDto,
    PettyCashMovementDto,
    PettyCashWitnessDto,
)

PROTOCOL_VERSION = 1
# Additive, optional features of protocol 1 (old clients ignore unknown fields; new clients check before relying).
CAPABILITIES = [
    "SUPERVISOR_INBOX_V1",
    "OP_METER_RESET_REQUEST",
    "OP_CASH_TRANSFER",  # CASH_TRANSFER, CASH_TRANSFER_ACKNOWLEDGEMENT, CASH_FLOAT_ACKNOWLEDGEMENT
    "OP_HOURS_PURCHASE",  # walk-in/registered customer hours purchase (+ payment claim and evidence uploads)
    "OP_HOURS_TRANSFER_REQUEST",
    "METER_DAILY_READING",  # METER_CAPTURE: a DAILY reading of a machine (machine_id)
    "OP_METER_BASELINE",
    "OP_METER_CORRECTION",
    "OP_CASH_RETENTION_REQUEST",  # CASH_RETENTION_REQUEST (ask to keep field cash; approved by another person)
    # CASH_HANDOVER accepts method, deposit_account_id, evidence_attachment_ids and evidence_upload_ids (purpose
    # REMITTANCE_EVIDENCE); SyncData.deposit_accounts carries the account picker (DEC-031 D2)
    "REMITTANCE_DETAILS_V1",
    # DAILY_REPORT {id, machine_id, report_date, opening_ref, closing_ref, billable_hours?, unbillable[], note?,
    # evidence_attachment_ids?, evidence_upload_ids? (purpose DAILY_REPORT_EVIDENCE), supersedes_id?, client_created_at}
    "OP_DAILY_REPORT",
    "SYNC_UNBILLABLE_REASONS",  # SyncData.unbillable_reasons: tenant list for daily reports (capture permission)
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
    # ADR-008 §1: HOURS_PURCHASE accepts a payment line with method CREDIT (amount only; registered customers; at most
    # one): the sale creates its credit invoice (acked entity: credit_amount + credit_invoice). Field staff need the
    # tenant's CUSTOMER_HOURS field_credit_sales (else CONFLICT CREDIT_SALES_NOT_ALLOWED, kept: money changed hands).
    "OP_HOURS_SALE_CREDIT",
    # ADR-008 §1: CREDIT_INVOICE_PAYMENT {invoice_id, amount, method CASH|BANK|MOBILE_MONEY, reference?, received_at,
    # staff_member_id?, note?, evidence_attachment_ids?, evidence_upload_ids? (purpose PAYMENT_EVIDENCE)}; op id =
    # client id. Cash goes into the recorder's custody. SyncData.open_credit_invoices: the picker (full snapshot).
    "OP_CREDIT_INVOICE_PAYMENT",
    # ADR-008 §2: MACHINE_REPORT (payload MachineReportIn; op id = report id) and SyncData.machine_report_* (reasons,
    # per-machine state, customers' available hours, the caller's own reports; full snapshots). See
    # docs/api-machine-reports.md.
    "OP_MACHINE_REPORT",
]
# Protocol capabilities that belong to a tenant capability (`asseta.modules.policy.capabilities`): not announced
# while the tenant has it switched off, and their operations are then refused (CONFLICT, the capability's code).
TENANT_CAPABILITY_OF = {
    "OP_HOURS_PURCHASE": "CUSTOMER_HOURS",
    "OP_HOURS_TRANSFER_REQUEST": "CUSTOMER_HOURS",
    "OP_METER_BASELINE": "ENGINE_HOURS",
    "OP_METER_CORRECTION": "ENGINE_HOURS",
    "OP_CASH_TRANSFER": "CASH_CUSTODY",
    "OP_CASH_RETENTION_REQUEST": "CASH_CUSTODY",
    "OP_DAILY_REPORT": "ENGINE_HOURS",
    "SYNC_UNBILLABLE_REASONS": "ENGINE_HOURS",
    "OP_PETTY_CASH": "PETTY_CASH",
    "OP_PETTY_CASH_ADVANCE": "PETTY_CASH",
    "SYNC_PETTY_CASH_WITNESSES": "PETTY_CASH",
    "SYNC_HOURS_PRICES": "CUSTOMER_HOURS",
    "OP_HOURS_SALE_CREDIT": "CUSTOMER_HOURS",
    "OP_CREDIT_INVOICE_PAYMENT": "CUSTOMER_HOURS",
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


class SyncUnbillableReasonDto(BaseModel):
    """One entry of the tenant's unbillable-reason list for the daily report (DEC-032 A4)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    sync_revision: int


class SyncData(BaseModel):
    # The machines assigned to the caller, the company's active sites and its active customers (bootstrap; deltas:
    # changes since the cursor, deactivations included, is_active=false).
    machines: list[MachineDto] = []
    sites: list[JobSiteDto] = []
    customers: list[CustomerDto] = []
    staff: list[StaffDto] = []
    expense_categories: list[ExpenseCategoryDto] = []
    cash_custody: list[CashCustodyBalanceDto] = []  # the signed-in supervisor's current custody (server-owned)
    # Company deposit accounts for the remittance picker (REMITTANCE_DETAILS_V1; cash recorders only). Bootstrap:
    # active accounts; deltas: changes since the cursor, deactivations included (is_active=false).
    deposit_accounts: list[SyncDepositAccountDto] = []
    # SYNC_UNBILLABLE_REASONS: bootstrap: active entries; deltas: changes since the cursor, deactivations included.
    unbillable_reasons: list[SyncUnbillableReasonDto] = []
    # Supervisor inbox (SUPERVISOR_INBOX_V1): the caller's own field records, upsert by (id, sync_revision).
    # Bootstrap: last 30 days + everything still open; deltas: anything changed since the cursor.
    my_meter_captures: list[SyncMeterCaptureDto] = []
    my_meter_resets: list[SyncMeterResetDto] = []
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
    # OP_MACHINE_REPORT (full snapshots on every bootstrap and delta; replace the local sets), for people who submit
    # machine reports: the reason list, the state of their machines (where a new report starts, a pending report),
    # customers' available hours (activated - used - reserved; per machine when the tenant's scope is MACHINE) and
    # their own reports of the last 30 days plus any still waiting for a decision.
    machine_report_reasons: list[MachineReportReasonDto] = []
    machine_report_states: list[MachineReportStatusDto] = []
    machine_report_hours: list[AvailableHoursDto] = []
    my_machine_reports: list[MachineReportDto] = []
    # OP_CREDIT_INVOICE_PAYMENT (full snapshot): open credit invoices (UNPAID / PART_PAID) for people who record
    # credit-invoice payments.
    open_credit_invoices: list[CreditInvoiceDto] = []


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
    "EXPENSE",
    "CASH_COLLECTION",
    "CASH_HANDOVER",
    "CASH_TRANSFER",  # field-to-field cash transfer (payload CashTransferIn, client_id required)
    "CASH_TRANSFER_ACKNOWLEDGEMENT",  # {transfer_id, acknowledged, amount_received?, note?}
    "CASH_FLOAT_ACKNOWLEDGEMENT",  # {entry_id, acknowledged, amount_received?, note?}
    "FUEL_EVENT",
    "METER_RESET_REQUEST",
    "HOURS_PURCHASE",  # customer hours purchase recorded in the field (payment stays CLAIMED until verified)
    "HOURS_TRANSFER_REQUEST",  # request to move remaining hours to another machine (approved per tenant policy)
    "METER_BASELINE",  # baseline proposal (engine-hour accountability)
    "METER_CORRECTION",  # reading correction proposal (approved by a second person)
    "CASH_RETENTION_REQUEST",  # payload CashRetentionIn, client_id required (tenant policy cash.retention_allowed)
    "DAILY_REPORT",  # payload DailyReportIn (op id = report id) + evidence_upload_ids (DEC-032 A4)
    "PETTY_CASH_ACKNOWLEDGEMENT",  # {movement_id, acknowledged, amount_received?, note?} (DEC-033)
    "PETTY_CASH_TOP_UP_REQUEST",  # {fund_id, amount?, note?, above_cap_reason?} (op id = client id)
    "PETTY_CASH_RETURN",  # PettyCashReturnIn (op id = client id) + evidence_upload_ids
    "PETTY_CASH_COUNT",  # PettyCashCountIn (op id = client id) + evidence_upload_ids
    "PETTY_CASH_ADVANCE_CLEARANCE",  # {advance_id, change_returned, note?}
    "PETTY_CASH_HOLDER_CHANGE_ACKNOWLEDGEMENT",  # {holder_change_id, accept, note?}
    "PETTY_CASH_ADVANCE",  # PettyCashAdvanceIn {fund_id, recipient_staff_id, amount, purpose} (op id = client id)
    "MACHINE_REPORT",  # MachineReportIn (op id = report id) + photo_upload_id (ADR-008 §2)
    "CREDIT_INVOICE_PAYMENT",  # CreditInvoicePaymentIn + invoice_id (op id = client id) + evidence_upload_ids
]


OP_TYPES: frozenset[str] = frozenset(get_args(OpType))
# Operation types of app versions before ADR-008 (jobs, work log, site check-ins). Phones that still queue them get
# each one REJECTED (OPERATION_RETIRED) and the rest of their batch applied, never a failed push.
RETIRED_OP_TYPES = frozenset({"JOB_ACTIVITY", "JOB_ACKNOWLEDGEMENT", "JOB_TRANSITION", "JOB_REQUEST", "SITE_CHECKIN"})


class OperationIn(BaseModel):
    id: uuid.UUID = Field(description="Device-generated operation id (idempotency key)")
    # The contract names the supported types (OpType); any other string is accepted here so that one retired or
    # unknown operation is refused on its own (push.py) instead of failing the whole batch with a 422.
    op_type: Annotated[str, WithJsonSchema({"enum": list(get_args(OpType)), "type": "string"})] = Field(max_length=40)
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
