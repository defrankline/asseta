"""Accountability oversight DTOs: security events, sync-conflict review and the dashboard summary (design D)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from asseta.modules.accountability.models import SecurityEventKind, SyncResolutionOutcome
from asseta.modules.platform_billing.dto import Money, Reason


class SecurityEventDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    occurred_at: datetime
    kind: SecurityEventKind
    actor_user_id: uuid.UUID | None
    actor_subject: str | None
    actor_display_name: str | None = None
    permission: str | None
    action: str | None
    entity_type: str | None
    entity_id: str | None
    request_method: str | None
    request_path: str | None
    detail: dict[str, Any]


# --- sync conflicts ------------------------------------------------------------------------------------------
class SyncResolutionIn(BaseModel):
    outcome: SyncResolutionOutcome
    reason: Reason
    recaptured_entity_type: str | None = Field(default=None, max_length=40, pattern=r"^[a-z_]+$")
    recaptured_entity_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _shape(self) -> "SyncResolutionIn":
        if (self.recaptured_entity_type is None) != (self.recaptured_entity_id is None):
            raise ValueError("give both recaptured_entity_type and recaptured_entity_id, or neither")
        if self.outcome is SyncResolutionOutcome.DISMISSED and self.recaptured_entity_id is not None:
            raise ValueError("a dismissed operation names no re-captured record")
        return self


class SyncResolutionDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    outcome: SyncResolutionOutcome
    reason: str
    recaptured_entity_type: str | None
    recaptured_entity_id: uuid.UUID | None
    resolved_by: uuid.UUID | None
    resolved_by_name: str | None = None
    resolved_at: datetime


class SyncConflictDto(BaseModel):
    """A field operation the server did not apply (CONFLICT or REJECTED), with what the device sent (evidence), why
    it was not applied, the server state at the time and the office's outcome once resolved."""

    operation_id: uuid.UUID
    op_type: str
    status: Literal["CONFLICT", "REJECTED"]
    error_code: str | None
    error_message: str | None
    server_state: dict[str, Any]
    payload: dict[str, Any]
    created_at_device: datetime
    received_at: datetime
    attempts: int
    device_id: str
    device_platform: str
    submitted_by: uuid.UUID
    submitted_by_name: str | None
    resolution: SyncResolutionDto | None


# --- dashboard -----------------------------------------------------------------------------------------------
class CountAmountDto(BaseModel):
    currency: str
    count: int
    amount: Money


class CustodianCashDto(BaseModel):
    staff_member_id: uuid.UUID
    staff_name: str
    currency: str
    outstanding: Money
    in_transit_out: Money
    claimed_unverified_handovers: Money
    pending_floats: Money


class CashTileDto(BaseModel):
    """[3.6.5]-[3.6.7] Cash per custodian, transfers awaiting acknowledgement, remittances awaiting confirmation."""

    custodians: list[CustodianCashDto]
    transfers_awaiting_acknowledgement: list[CountAmountDto]
    floats_awaiting_acknowledgement: list[CountAmountDto]
    remittances_awaiting_confirmation: list[CountAmountDto]
    partial_remittances_in_window: int
    remittance_cutoff_hour: int | None = Field(
        default=None, description="Tenant-local daily remittance cut-off (cash policy); null = no cut-off"
    )
    remittances_overdue_today: int | None = Field(
        default=None,
        description="Custodians flagged today for unremitted cash past the cut-off or held longer than allowed "
        "(REMITTANCE_OVERDUE); null = no cut-off or holding allowance configured",
    )


class PaymentsTileDto(BaseModel):
    """[3.6.8] Customer payments claimed but not yet confirmed by the office."""

    awaiting_confirmation: list[CountAmountDto]


class InvestigationsTileDto(BaseModel):
    """[3.6.4] Open and in-review investigation cases."""

    open: int
    in_review: int


class DiscrepanciesTileDto(BaseModel):
    """[3.6.10] Unresolved cash variances and offline operations awaiting review."""

    open_variances: list[CountAmountDto]
    write_offs_proposed: int
    sync_conflicts_unresolved: int


class AttemptsTileDto(BaseModel):
    """[3.6.10] Refused attempts in the policy window."""

    window_days: int
    permission_denied: int
    segregation_of_duties: int


class ApprovalsTileDto(BaseModel):
    """[3.6.10] Outstanding approvals across modules."""

    approval_requests: int
    cash_retentions: int
    custody_adjustments: int
    write_offs: int
    payments_to_verify: int
    remittances_to_verify: int
    total: int


class AccountabilitySummaryDto(BaseModel):
    """The 3.6 oversight list. A tile is null when hidden (`hidden_tiles`: by the tenant's OVERSIGHT policy, or
    because the tenant switched its capability off) or when the capability behind it is not available in this
    deployment (`unavailable_tiles` names those)."""

    as_of: datetime
    policy_version: str
    hidden_tiles: list[str]
    unavailable_tiles: list[str]
    disabled_capabilities: list[str] = Field(
        default_factory=list,
        description="Tenant capabilities switched off by policy (CUSTOMER_HOURS, ENGINE_HOURS, CASH_CUSTODY); their "
        "tiles are hidden and, for CASH_CUSTODY, the cash-control figures of the cash/discrepancy/approval tiles are "
        "empty",
    )
    customer_hours: dict[str, Any] | None = Field(
        default=None, description="[3.6.2] purchased/activated/consumed/remaining (customer hours module)"
    )
    hours_awaiting_activation: dict[str, Any] | None = Field(
        default=None, description="[3.6.8] hours awaiting activation (customer hours module)"
    )
    engine_hours: dict[str, Any] | None = Field(
        default=None, description="[3.6.3] engine-hour reconciliation per machine (meter module)"
    )
    unexplained_hours: dict[str, Any] | None = Field(
        default=None, description="[3.6.4] unexplained engine hours (meter module)"
    )
    missing_daily_reports: dict[str, Any] | None = Field(
        default=None, description="[3.6.9] missing or overdue operational reports (meter module)"
    )
    investigations: InvestigationsTileDto | None = None
    cash: CashTileDto | None = None
    payments: PaymentsTileDto | None = None
    discrepancies: DiscrepanciesTileDto | None = None
    unauthorized_attempts: AttemptsTileDto | None = None
    outstanding_approvals: ApprovalsTileDto | None = None
