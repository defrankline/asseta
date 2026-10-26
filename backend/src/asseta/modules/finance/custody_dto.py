"""DTOs of the cash custody chain controls (transfers, float acknowledgements, variances, retentions, custody
adjustments, reason lists, custodians, reconciliation drill-down). Money is serialized as decimal strings."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field, model_validator

from asseta.modules.finance.custody_models import (
    AcknowledgementMethod,
    CashDecisionStatus,
    CashReasonKind,
    CashTransferStatus,
    CustodyAdjustmentKind,
    OverdueReason,
    VarianceOutcome,
    VarianceSource,
    VarianceStatus,
)
from asseta.modules.finance.dto import Note, PositiveAmount
from asseta.modules.fleet.models import StaffKind
from asseta.modules.platform_billing.dto import CurrencyCode, Money, Reason

NonNegativeAmount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
SignedAmount = Annotated[Decimal, Field(max_digits=18, decimal_places=4)]
Label = Annotated[str, StringConstraints(min_length=2, max_length=120, strip_whitespace=True)]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- custodians --------------------------------------------------------------------------------------------
class CustodianDto(BaseModel):
    """A staff member who can hold company cash. A login is not required (custodians without one are recorded for
    by recorders when the tenant allows it)."""

    staff_member_id: uuid.UUID
    full_name: str
    kind: StaffKind
    employee_code: str | None
    is_active: bool
    has_login: bool


# --- transfers ---------------------------------------------------------------------------------------------
class CashTransferIn(BaseModel):
    client_id: uuid.UUID | None = Field(default=None, description="Device/client id (offline idempotency)")
    from_staff_id: uuid.UUID | None = Field(default=None, description="Sender; defaults to the caller's staff record")
    to_staff_id: uuid.UUID
    amount: PositiveAmount = Field(description="Amount declared by the sender")
    currency: CurrencyCode | None = None
    transferred_at: datetime
    note: Note | None = None
    amount_received: NonNegativeAmount | None = Field(
        default=None,
        description="Only when the recorder is the receiver (and the tenant counts that as acknowledgement): the "
        "amount actually received; defaults to the declared amount",
    )


class CashAcknowledgementIn(BaseModel):
    """Receiver's answer: acknowledge with the amount actually received, or dispute (nothing received)."""

    acknowledged: bool
    amount_received: NonNegativeAmount | None = Field(
        default=None, description="Acknowledgement only; defaults to the declared amount"
    )
    note: Note | None = None

    @model_validator(mode="after")
    def _dispute(self) -> "CashAcknowledgementIn":
        if not self.acknowledged and self.amount_received is not None:
            raise ValueError("a dispute carries no amount_received")
        return self


class CashTransferDto(Dto):
    id: uuid.UUID
    client_id: uuid.UUID | None
    from_staff_id: uuid.UUID
    from_staff_name: str | None = None
    to_staff_id: uuid.UUID
    to_staff_name: str | None = None
    amount_declared: Money
    currency: str
    transferred_at: datetime
    note: str | None
    status: CashTransferStatus
    source: str
    recorded_by: uuid.UUID | None
    recorded_by_name: str | None = None
    recorded_at: datetime
    amount_received: Money | None
    ack_method: AcknowledgementMethod | None
    acknowledged_by: uuid.UUID | None
    acknowledged_by_name: str | None = None
    acknowledged_at: datetime | None
    ack_note: str | None
    variance_id: uuid.UUID | None = None


# --- variances ---------------------------------------------------------------------------------------------
class CashVarianceDto(Dto):
    id: uuid.UUID
    source_type: VarianceSource
    source_id: uuid.UUID
    staff_member_id: uuid.UUID | None = Field(description="Custodian accountable for the difference")
    staff_member_name: str | None = None
    counterparty_staff_id: uuid.UUID | None
    counterparty_staff_name: str | None = None
    currency: str
    declared_amount: Money
    received_amount: Money
    amount: Money = Field(description="declared - received (negative: more received than declared)")

    @computed_field(description="SHORTFALL: less received than declared; SURPLUS: more ('Surplus to explain')")
    def kind(self) -> Literal["SHORTFALL", "SURPLUS"]:
        return "SURPLUS" if self.amount < 0 else "SHORTFALL"

    case_id: uuid.UUID | None
    opened_at: datetime
    opened_by: uuid.UUID | None
    opened_by_name: str | None = None
    status: VarianceStatus
    reason_id: uuid.UUID | None
    proposed_by: uuid.UUID | None
    proposed_by_name: str | None = None
    proposed_at: datetime | None
    proposal_note: str | None
    outcome: VarianceOutcome | None
    resolved_by: uuid.UUID | None
    resolved_by_name: str | None = None
    resolved_at: datetime | None
    resolution_note: str | None


class VarianceResolutionIn(BaseModel):
    outcome: VarianceOutcome
    note: Reason
    reason_id: uuid.UUID | None = None


class WriteOffProposalIn(BaseModel):
    note: Reason
    reason_id: uuid.UUID | None = None


class DecisionIn(BaseModel):
    approve: bool
    note: Note | None = None


# --- retentions --------------------------------------------------------------------------------------------
class CashRetentionIn(BaseModel):
    client_id: uuid.UUID | None = Field(default=None, description="Device/client id (offline idempotency)")
    staff_member_id: uuid.UUID | None = Field(default=None, description="Defaults to the caller's staff record")
    amount: PositiveAmount
    currency: CurrencyCode | None = None
    reason: Reason
    reason_id: uuid.UUID | None = None
    valid_until: datetime | None = None


class CashRetentionDto(Dto):
    id: uuid.UUID
    client_id: uuid.UUID | None = None
    staff_member_id: uuid.UUID
    staff_member_name: str | None = None
    amount: Money
    currency: str
    reason_id: uuid.UUID | None
    reason: str
    valid_until: datetime | None
    status: CashDecisionStatus
    created_by: uuid.UUID | None
    created_by_name: str | None = None
    created_at: datetime
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None


# --- remittance cut-off ------------------------------------------------------------------------------------
class OverdueAmountDto(BaseModel):
    currency: str
    amount: Money = Field(description="Unremitted when flagged: outstanding - claimed remittances - retentions")


class RemittanceOverdueDto(Dto):
    """A custodian still holding unremitted cash after the tenant's daily cut-off (reason CUTOFF) or longer than
    their holding allowance (reason HELD_TOO_LONG). One per custodian per tenant-local day per reason; evidence,
    never edited."""

    id: uuid.UUID
    staff_member_id: uuid.UUID
    staff_member_name: str | None = None
    local_day: date
    cutoff_hour: int = Field(
        description="CUTOFF: the daily cut-off hour; HELD_TOO_LONG: the tenant-local hour when it was flagged"
    )
    amounts: list[OverdueAmountDto]
    flagged_at: datetime
    policy_version: str
    reason: OverdueReason = OverdueReason.CUTOFF
    held_since: datetime | None = Field(default=None, description="When the oldest unremitted cash was received")
    max_holding_days: int | None = Field(default=None, description="The holding allowance that applied")


# --- custody adjustments -----------------------------------------------------------------------------------
ReversibleEntity = Literal[
    "customer_payment", "cash_handover", "cash_transfer", "supervisor_cash_custody", "expense", "custody_adjustment"
]


class CustodyAdjustmentIn(BaseModel):
    staff_member_id: uuid.UUID
    kind: CustodyAdjustmentKind
    amount: SignedAmount = Field(description="Signed: positive raises the expected balance, negative lowers it")
    currency: CurrencyCode | None = None
    reason: Reason
    reason_id: uuid.UUID | None = None
    reverses_entity_type: ReversibleEntity | None = None
    reverses_entity_id: uuid.UUID | None = None
    occurred_at: datetime | None = None

    @model_validator(mode="after")
    def _shape(self) -> "CustodyAdjustmentIn":
        if self.amount == 0:
            raise ValueError("amount must not be zero")
        if (self.reverses_entity_type is None) != (self.reverses_entity_id is None):
            raise ValueError("give both reverses_entity_type and reverses_entity_id, or neither")
        if self.kind is CustodyAdjustmentKind.REVERSAL and self.reverses_entity_id is None:
            raise ValueError("a reversal names the record it reverses")
        return self


class CustodyAdjustmentDto(Dto):
    id: uuid.UUID
    staff_member_id: uuid.UUID
    staff_member_name: str | None = None
    kind: CustodyAdjustmentKind
    amount: Money
    currency: str
    occurred_at: datetime
    reason_id: uuid.UUID | None
    reason: str
    reverses_entity_type: str | None
    reverses_entity_id: uuid.UUID | None
    status: CashDecisionStatus
    created_by: uuid.UUID | None
    created_by_name: str | None = None
    created_at: datetime
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None


# --- reason lists (tenant data) ----------------------------------------------------------------------------
class CashReasonIn(BaseModel):
    kind: CashReasonKind
    label: Label
    description: Note | None = None


class CashReasonUpdateIn(BaseModel):
    label: Label | None = None
    description: Note | None = None
    version: int | None = Field(default=None, ge=1)


class CashReasonDto(Dto):
    id: uuid.UUID
    kind: CashReasonKind
    label: str
    description: str | None
    is_active: bool
    version: int
    created_at: datetime
    deactivated_at: datetime | None
    deactivation_reason: str | None


# --- reconciliation drill-down -----------------------------------------------------------------------------
class ReconciliationFigure(StrEnum):
    """A reconciliation figure (the field name on the daily reconciliation) a transaction contributes to."""

    FLOATS_ISSUED = "floats_issued"
    COLLECTIONS = "collections"
    TRANSFERS_IN = "transfers_in"
    TRANSFERS_OUT = "transfers_out"
    APPROVED_SPENDING = "approved_spending"
    VERIFIED_HANDOVERS = "verified_handovers"
    ADJUSTMENTS = "adjustments"
    WRITTEN_OFF = "written_off"
    CLAIMED_UNVERIFIED_HANDOVERS = "claimed_unverified_handovers"
    PENDING_SPENDING = "pending_spending"
    UNVERIFIED_COLLECTIONS = "unverified_collections"
    IN_TRANSIT_OUT = "in_transit_out"
    IN_TRANSIT_IN = "in_transit_in"
    PENDING_FLOATS = "pending_floats"
    PENDING_ADJUSTMENTS = "pending_adjustments"


class CustodyTransactionDto(BaseModel):
    """One transaction behind a reconciliation figure, with the record to open for its evidence."""

    figure: ReconciliationFigure
    occurred_at: datetime
    amount: Money = Field(description="Contribution to the figure (adjustments and write-offs are signed)")
    currency: str
    entity_type: str
    entity_id: uuid.UUID
    status: str
    reference: str | None
    note: str | None
    recorded_by: uuid.UUID | None
    recorded_by_name: str | None = None
    counterparty_staff_id: uuid.UUID | None
    counterparty_staff_name: str | None = None
