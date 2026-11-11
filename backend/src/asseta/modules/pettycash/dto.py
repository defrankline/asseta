"""Petty cash DTOs (DEC-033). Money is serialized as decimal strings; `*_name` fields are filled by `named`."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from asseta.modules.finance.custody_models import AcknowledgementMethod, CashDecisionStatus
from asseta.modules.finance.deposit_models import RemittanceMethod
from asseta.modules.finance.dto import Note, PositiveAmount, Ref
from asseta.modules.pettycash.models import (
    AdvanceStatus,
    CountReason,
    HolderChangeStatus,
    MovementKind,
    MovementStatus,
)
from asseta.modules.platform_billing.dto import CurrencyCode, Money, Reason

NonNegativeAmount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
SignedAmount = Annotated[Decimal, Field(max_digits=18, decimal_places=4)]
Code = Annotated[str, StringConstraints(min_length=1, max_length=32, strip_whitespace=True)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]
Evidence = Annotated[list[uuid.UUID], Field(default_factory=list, max_length=20)]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FundFigure(StrEnum):
    """A figure of the fund ledger (the field name on the balance) a transaction contributes to."""

    FUNDED = "funded"  # fundings and top-ups acknowledged by the holder (amount received)
    SPENT = "spent"  # approved expenses paid from the fund (not those of an advance)
    RETURNED = "returned"  # returns confirmed by the office (amount counted)
    ADJUSTMENTS = "adjustments"  # approved adjustments (signed)
    WRITTEN_OFF = "written_off"  # written-off count and return differences (signed)
    ADVANCES_ISSUED = "advances_issued"
    ADVANCE_CHANGE_RETURNED = "advance_change_returned"  # change handed back on cleared advances
    PENDING_SPENDING = "pending_spending"  # fund expenses waiting for approval
    AWAITING_ACKNOWLEDGEMENT = "awaiting_acknowledgement"  # fundings / top-ups issued, not yet acknowledged
    RETURNS_CLAIMED = "returns_claimed"  # returns the office has not confirmed yet
    OPEN_RETURN_DIFFERENCES = "open_return_differences"  # unresolved return differences (cash already gone)
    PENDING_ADJUSTMENTS = "pending_adjustments"
    ADVANCES_OUTSTANDING = "advances_outstanding"  # advances not cleared yet (already out of the fund)
    ADVANCE_SPENDING = "advance_spending"  # approved expenses of advances (paid from advance cash; not counted again)


# --- funds -------------------------------------------------------------------------------------------------------
class PettyCashFundIn(BaseModel):
    code: Code
    name: Name
    holder_staff_id: uuid.UUID
    job_site_id: uuid.UUID | None = None
    currency: CurrencyCode | None = Field(default=None, description="Defaults to the tenant currency")
    approved_limit: PositiveAmount
    low_balance_level: NonNegativeAmount | None = None
    note: Note | None = None


class PettyCashFundUpdateIn(BaseModel):
    code: Code
    name: Name
    job_site_id: uuid.UUID | None = None
    approved_limit: PositiveAmount
    low_balance_level: NonNegativeAmount | None = None
    note: Note | None = None
    version: int = Field(ge=1, description="Optimistic concurrency token from the last read")


class PettyCashBalanceDto(BaseModel):
    """A fund's ledger now. balance = funded - spent - returned + adjustments - written_off - advances_issued
    + advance_change_returned. The other figures are shown apart and never reduce accountability until confirmed;
    available_to_spend = balance - pending_spending - returns_claimed - open_return_differences (the cash expected in
    the box, also the expected figure of a count)."""

    fund_id: uuid.UUID
    fund_code: str
    fund_name: str
    currency: str
    holder_staff_id: uuid.UUID
    holder_staff_name: str | None = None
    is_active: bool
    approved_limit: Money
    low_balance_level: Money | None
    balance: Money
    available_to_spend: Money
    below_low_balance: bool
    funded: Money
    spent: Money
    returned: Money
    adjustments: Money
    written_off: Money
    advances_issued: Money
    advance_change_returned: Money
    pending_spending: Money
    awaiting_acknowledgement: Money
    returns_claimed: Money
    open_return_differences: Money
    pending_adjustments: Money
    advances_outstanding: Money
    advance_spending: Money
    last_count_at: datetime | None = None
    next_count_due_at: datetime | None = None
    as_of: datetime


class PettyCashFundDto(Dto):
    id: uuid.UUID
    code: str
    name: str
    holder_staff_id: uuid.UUID
    holder_staff_name: str | None = None
    job_site_id: uuid.UUID | None
    job_site_name: str | None = None
    currency: str
    approved_limit: Money
    low_balance_level: Money | None
    note: str | None
    is_active: bool
    version: int
    created_by: uuid.UUID | None
    created_by_name: str | None = None
    created_at: datetime
    deactivated_at: datetime | None
    deactivated_by: uuid.UUID | None
    deactivated_by_name: str | None = None
    deactivation_reason: str | None
    pending_holder_change_id: uuid.UUID | None = None
    balance: PettyCashBalanceDto | None = None


class PettyCashTransactionDto(BaseModel):
    """One record behind a fund figure, with the record to open for its evidence."""

    figure: FundFigure
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


class PettyCashStatementLineDto(BaseModel):
    occurred_at: datetime
    figure: FundFigure
    entity_type: str
    entity_id: uuid.UUID
    reference: str | None
    note: str | None
    money_in: Money
    money_out: Money
    running_balance: Money


class PettyCashStatementDto(BaseModel):
    fund_id: uuid.UUID
    currency: str
    timezone: str
    date_from: date
    date_to: date
    opening_balance: Money
    closing_balance: Money
    lines: list[PettyCashStatementLineDto]


class TopUpExpenseDto(BaseModel):
    id: uuid.UUID
    description: str
    amount: Money
    incurred_at: datetime
    decided_at: datetime | None
    category_id: uuid.UUID
    machine_id: uuid.UUID | None
    job_id: uuid.UUID | None


class TopUpSuggestionDto(BaseModel):
    """Imprest: approved spending since the last issued funding or top-up, capped at limit - balance - money already
    on its way (proposed, approved or issued). The proposer may lower it; above the cap needs a reason."""

    fund_id: uuid.UUID
    currency: str
    balance: Money
    approved_limit: Money
    in_flight: Money
    cap: Money
    since: datetime | None
    spending_since: Money
    suggested: Money
    expenses: list[TopUpExpenseDto]


# --- movements ---------------------------------------------------------------------------------------------------
class PettyCashFundingIn(BaseModel):
    client_id: uuid.UUID | None = Field(default=None, description="Device/client id (offline idempotency)")
    fund_id: uuid.UUID
    kind: Literal[MovementKind.FUNDING, MovementKind.TOP_UP]
    amount: PositiveAmount | None = Field(
        default=None, description="TOP_UP defaults to the suggested imprest amount; FUNDING requires it"
    )
    deposit_account_id: uuid.UUID | None = Field(default=None, description="Where the money comes from")
    method: RemittanceMethod | None = None
    reference: Ref | None = None
    note: Note | None = None
    above_cap_reason: Reason | None = Field(default=None, description="Required when the amount is above the cap")
    client_created_at: datetime | None = None


class TopUpRequestIn(BaseModel):
    """The holder asks for a top-up (the office approves and issues it; the holder never approves it)."""

    client_id: uuid.UUID | None = None
    amount: PositiveAmount | None = Field(default=None, description="Defaults to the suggested imprest amount")
    note: Note | None = None
    above_cap_reason: Reason | None = None
    client_created_at: datetime | None = None


class PettyCashDecisionIn(BaseModel):
    approve: bool
    note: Note | None = None


class PettyCashIssueIn(BaseModel):
    deposit_account_id: uuid.UUID | None = None
    method: RemittanceMethod | None = None
    reference: Ref | None = None
    evidence_attachment_ids: Evidence
    note: Note | None = None


class PettyCashAcknowledgementIn(BaseModel):
    """The holder's answer: acknowledge with the amount actually received, or dispute (nothing received)."""

    acknowledged: bool
    amount_received: NonNegativeAmount | None = Field(default=None, description="Defaults to the amount issued")
    note: Note | None = None

    @model_validator(mode="after")
    def _dispute(self) -> "PettyCashAcknowledgementIn":
        if not self.acknowledged and self.amount_received is not None:
            raise ValueError("a dispute carries no amount_received")
        return self


class PettyCashReturnIn(BaseModel):
    client_id: uuid.UUID | None = None
    fund_id: uuid.UUID
    amount: PositiveAmount
    deposit_account_id: uuid.UUID | None = Field(default=None, description="Where the money went")
    method: RemittanceMethod | None = None
    reference: Ref | None = None
    note: Note | None = None
    evidence_attachment_ids: Evidence
    client_created_at: datetime | None = None


class PettyCashReturnConfirmIn(BaseModel):
    amount_received: NonNegativeAmount = Field(description="What the office counted")
    note: Note | None = None


class PettyCashMovementDto(Dto):
    id: uuid.UUID
    number: str
    fund_id: uuid.UUID
    petty_cash_fund_name: str | None = None
    kind: MovementKind
    status: MovementStatus
    client_id: uuid.UUID | None
    holder_staff_id: uuid.UUID
    holder_staff_name: str | None = None
    amount: Money
    currency: str
    deposit_account_id: uuid.UUID | None
    deposit_account_name: str | None = None
    method: str | None
    reference: str | None
    note: str | None
    suggested_amount: Money | None
    cap_amount: Money | None
    above_cap_reason: str | None
    basis_from: datetime | None
    evidence_attachment_ids: list[uuid.UUID]
    source: str
    created_by: uuid.UUID | None
    created_by_name: str | None = None
    created_at: datetime
    client_created_at: datetime | None
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None
    issued_by: uuid.UUID | None
    issued_by_name: str | None = None
    issued_at: datetime | None
    received_by: uuid.UUID | None
    received_by_name: str | None = None
    received_at: datetime | None
    amount_received: Money | None
    receipt_method: AcknowledgementMethod | None
    receipt_note: str | None
    variance_id: uuid.UUID | None = None


# --- counts ------------------------------------------------------------------------------------------------------
class PettyCashWitnessDto(BaseModel):
    """A login that may witness a count: active in the tenant and holding the petty cash count permission."""

    user_id: uuid.UUID
    name: str


class PettyCashCountIn(BaseModel):
    client_id: uuid.UUID | None = None
    fund_id: uuid.UUID
    counted_amount: NonNegativeAmount
    witness_user_id: uuid.UUID | None = Field(default=None, description="Another login holding the count permission")
    evidence_attachment_ids: Evidence
    note: Note | None = None
    client_created_at: datetime | None = None


class PettyCashCountDto(Dto):
    id: uuid.UUID
    number: str
    fund_id: uuid.UUID
    petty_cash_fund_name: str | None = None
    client_id: uuid.UUID | None
    reason: CountReason
    holder_staff_id: uuid.UUID
    holder_staff_name: str | None = None
    currency: str
    counted_amount: Money
    expected_amount: Money
    difference: Money = Field(description="counted - expected (negative: less cash than expected)")
    counted_by: uuid.UUID | None
    counted_by_name: str | None = None
    counted_at: datetime
    witness_user_id: uuid.UUID | None
    witness_user_name: str | None = None
    self_count: bool = Field(description="Counted by the holder alone while the tenant asks for a witness")
    evidence_attachment_ids: list[uuid.UUID]
    note: str | None
    source: str
    policy_version: str | None
    client_created_at: datetime | None
    variance_id: uuid.UUID | None = None


# --- holder changes ----------------------------------------------------------------------------------------------
class PettyCashHolderChangeIn(BaseModel):
    to_staff_id: uuid.UUID
    counted_amount: NonNegativeAmount = Field(description="The count at the change")
    witness_user_id: uuid.UUID | None = None
    evidence_attachment_ids: Evidence
    note: Note | None = None


class PettyCashHolderChangeDecisionIn(BaseModel):
    accept: bool
    note: Note | None = None


class PettyCashHolderChangeDto(Dto):
    id: uuid.UUID
    fund_id: uuid.UUID
    petty_cash_fund_name: str | None = None
    from_staff_id: uuid.UUID
    from_staff_name: str | None = None
    to_staff_id: uuid.UUID
    to_staff_name: str | None = None
    count_id: uuid.UUID
    status: HolderChangeStatus
    note: str | None
    requested_by: uuid.UUID | None
    requested_by_name: str | None = None
    requested_at: datetime
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None


# --- adjustments -------------------------------------------------------------------------------------------------
class PettyCashAdjustmentIn(BaseModel):
    fund_id: uuid.UUID
    amount: SignedAmount = Field(description="Signed: positive raises the fund balance, negative lowers it")
    reason: Reason
    reason_id: uuid.UUID | None = None
    evidence_attachment_ids: Evidence

    @model_validator(mode="after")
    def _non_zero(self) -> "PettyCashAdjustmentIn":
        if self.amount == 0:
            raise ValueError("amount must not be zero")
        return self


class PettyCashAdjustmentDto(Dto):
    id: uuid.UUID
    number: str
    fund_id: uuid.UUID
    petty_cash_fund_name: str | None = None
    amount: Money
    currency: str
    reason_id: uuid.UUID | None
    reason: str
    evidence_attachment_ids: list[uuid.UUID]
    status: CashDecisionStatus
    created_by: uuid.UUID | None
    created_by_name: str | None = None
    created_at: datetime
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None


# --- advances (phase 3) ------------------------------------------------------------------------------------------
class PettyCashAdvanceIn(BaseModel):
    client_id: uuid.UUID | None = None
    fund_id: uuid.UUID
    recipient_staff_id: uuid.UUID
    amount: PositiveAmount
    purpose: Reason
    client_created_at: datetime | None = None


class PettyCashAdvanceClearIn(BaseModel):
    change_returned: NonNegativeAmount
    note: Note | None = None


class PettyCashAdvanceDto(Dto):
    id: uuid.UUID
    number: str
    fund_id: uuid.UUID
    petty_cash_fund_name: str | None = None
    client_id: uuid.UUID | None
    recipient_staff_id: uuid.UUID
    recipient_staff_name: str | None = None
    amount: Money
    currency: str
    purpose: str
    status: AdvanceStatus
    issued_by: uuid.UUID | None
    issued_by_name: str | None = None
    issued_at: datetime
    due_at: datetime
    overdue: bool = False
    source: str
    client_created_at: datetime | None
    cleared_by: uuid.UUID | None
    cleared_by_name: str | None = None
    cleared_at: datetime | None
    spent_amount: Money | None
    change_returned: Money | None
    clear_note: str | None
    approved_spending: Money = Decimal(0)
    pending_spending: Money = Decimal(0)
    remaining: Money = Decimal(0)
    variance_id: uuid.UUID | None = None
