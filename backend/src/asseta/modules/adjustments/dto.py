"""Adjustments ledger and propose/decide DTOs. Display names beside ids are filled by the `@named` mechanism."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from asseta.modules.adjustments.models import (
    AdjustmentEntryStatus,
    AdjustmentRequestStatus,
    AdjustmentRequestType,
    AdjustmentType,
    AdjustmentUnit,
    RefundSettlement,
)
from asseta.modules.finance.models import HirePaymentMethod
from asseta.modules.platform_billing.dto import Money, Reason

Note = Annotated[str, StringConstraints(max_length=1000, strip_whitespace=True)]
Hours = Annotated[Decimal, Field(max_digits=12, decimal_places=2)]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AdjustmentEntryDto(Dto):
    """One decided adjustment (guideline 4.6 fields; `unit` says what `original_value`, `new_value`, `amount` and
    `resulting_balance` measure)."""

    id: uuid.UUID
    entry_number: str | None = None
    adjustment_type: AdjustmentType
    status: AdjustmentEntryStatus
    original_type: str
    original_id: uuid.UUID
    original_reference: str | None
    source_type: str
    source_id: uuid.UUID
    unit: AdjustmentUnit
    original_value: Decimal | None
    new_value: Decimal | None
    amount: Decimal | None
    currency: str | None
    resulting_balance: Decimal | None
    reason_id: uuid.UUID | None
    reason_label: str | None
    reason: str | None
    evidence_attachment_ids: list[uuid.UUID]
    customer_id: uuid.UUID | None
    customer_name: str | None = None
    machine_id: uuid.UUID | None
    machine_code: str | None = None
    machine_name: str | None = None
    staff_member_id: uuid.UUID | None
    staff_member_name: str | None = None
    requested_by: uuid.UUID | None
    requested_by_name: str | None = None
    requested_at: datetime | None
    approved_by: uuid.UUID | None
    approved_by_name: str | None = None
    approved_at: datetime | None
    decision_note: str | None
    details: dict[str, Any]
    posted_at: datetime


class PayoutIn(BaseModel):
    method: HirePaymentMethod
    reference: str | None = Field(default=None, max_length=120)
    staff_member_id: uuid.UUID | None = None  # the custodian paying it out of their cash (CASH): reduces their custody


class AdjustmentRequestIn(BaseModel):
    """Propose a correction, refund, reversal or invoice void. Which fields apply depends on `request_type`: see the
    endpoint notes (hours/machine for corrections and refunds, a payment/purchase/invoice id for reversals)."""

    model_config = ConfigDict(extra="forbid")

    client_id: uuid.UUID | None = None
    request_type: AdjustmentRequestType
    purchase_id: uuid.UUID | None = None
    machine_id: uuid.UUID | None = None
    hours: Hours | None = None  # signed for HOURS_CORRECTION; positive for HOURS_REFUND
    job_id: uuid.UUID | None = None  # HOURS_CORRECTION: the job whose consumption is being corrected
    consumed_entry_id: uuid.UUID | None = None  # HOURS_CORRECTION: the CONSUMED ledger entry being corrected
    settlement: RefundSettlement | None = None  # HOURS_REFUND
    payout: PayoutIn | None = None  # HOURS_REFUND with PAY_OUT
    payment_id: uuid.UUID | None = None  # PAYMENT_REVERSAL / COLLECTION_REVERSAL
    invoice_id: uuid.UUID | None = None  # INVOICE_VOID
    reason: Reason
    reason_code_id: uuid.UUID | None = None  # tenant list (hours reason codes of the matching kind)
    evidence_attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    client_created_at: datetime | None = None  # the device's time (offline), kept alongside the server's


class AdjustmentPreviewIn(AdjustmentRequestIn):
    """The same fields as a request; reason and evidence are not needed to see what it would do."""

    reason: Reason | None = None  # type: ignore[assignment]


class AdjustmentPreviewDto(BaseModel):
    """What the request would do, as of now, without saving anything (a `refused` entry names why it would fail)."""

    request_type: AdjustmentRequestType
    original_type: str
    original_id: uuid.UUID
    original_reference: str | None
    customer_id: uuid.UUID | None
    customer_name: str | None = None
    machine_id: uuid.UUID | None
    machine_code: str | None = None
    machine_name: str | None = None
    purchase_id: uuid.UUID | None
    hours: Decimal | None
    amount: Money | None
    currency: str | None
    effects: dict[str, Any] = {}


class AdjustmentDecisionIn(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    note: Note | None = None


class AdjustmentWithdrawIn(BaseModel):
    reason: Reason


class AdjustmentRequestDto(Dto):
    id: uuid.UUID
    request_number: str | None = None
    client_created_at: datetime | None = None
    client_id: uuid.UUID | None
    request_type: AdjustmentRequestType
    status: AdjustmentRequestStatus
    original_type: str
    original_id: uuid.UUID
    original_reference: str | None
    customer_id: uuid.UUID | None
    customer_name: str | None = None
    machine_id: uuid.UUID | None
    machine_code: str | None = None
    machine_name: str | None = None
    purchase_id: uuid.UUID | None
    purchase_number: str | None = None
    hours: Decimal | None
    amount: Money | None
    currency: str | None
    settlement: RefundSettlement | None
    params: dict[str, Any]
    reason: str
    reason_code_id: uuid.UUID | None
    reason_label: str | None = None
    evidence_attachment_ids: list[uuid.UUID]
    proposed_by: uuid.UUID | None
    proposed_by_name: str | None = None
    proposed_at: datetime
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None
    effects: dict[str, Any] = {}  # forecast while PROPOSED; what the approval did once decided
