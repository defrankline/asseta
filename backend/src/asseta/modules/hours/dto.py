"""Customer hours DTOs. Hours and money are decimal strings; every amount carries its currency."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from asseta.modules.finance.dto import CustomerPaymentDto
from asseta.modules.finance.models import HirePaymentMethod
from asseta.modules.hours.models import (
    ActivationSource,
    LedgerEntryType,
    ProposalStatus,
    ReasonKind,
    RequestStatus,
)
from asseta.modules.jobs.models import CustomerKind
from asseta.modules.platform_billing.dto import CurrencyCode, Money, Reason

PositiveHours = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
PositiveAmount = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]
Percent = Annotated[Decimal, Field(gt=0, le=100, max_digits=7, decimal_places=4)]
Note = Annotated[str, StringConstraints(max_length=1000, strip_whitespace=True)]
Ref = Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
Code = Annotated[str, StringConstraints(min_length=1, max_length=32, strip_whitespace=True)]
Phone = Annotated[str, StringConstraints(min_length=3, max_length=40, strip_whitespace=True)]
PurchaseStatus = Literal["AWAITING_PAYMENT", "PARTLY_ACTIVE", "ACTIVE", "CONSUMED", "EXPIRED", "CANCELLED"]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DecisionIn(BaseModel):
    approve: bool
    note: Note | None = None


class ReasonIn(BaseModel):
    reason: Reason


# --- walk-in customers ------------------------------------------------------------------------------------------
class WalkInCustomerIn(BaseModel):
    """A walk-in needs only a display name (phone optional); the code WALK-<nnnnn> is assigned by the server."""

    name: Name
    phone: Phone | None = None
    client_id: uuid.UUID | None = Field(
        default=None, description="Device-generated id; becomes the customer id (offline replays return it)"
    )


class CustomerRegistrationIn(BaseModel):
    """Upgrade a walk-in to a registered customer (audited); history stays with the same customer record."""

    code: Code
    name: Name | None = None
    tax_id: str | None = Field(default=None, max_length=64)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320)
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)
    version: int | None = Field(default=None, ge=1)


class WalkInCustomerDto(Dto):
    id: uuid.UUID
    code: str
    name: str
    contact_phone: str | None
    kind: CustomerKind
    is_active: bool
    version: int


# --- reason lists (tenant data) ---------------------------------------------------------------------------------
class ReasonCodeIn(BaseModel):
    kind: ReasonKind
    code: Code
    label: Name


class ReasonCodeUpdateIn(BaseModel):
    code: Code
    label: Name
    version: int = Field(ge=1)


class ReasonCodeDto(Dto):
    id: uuid.UUID
    kind: ReasonKind
    code: str
    label: str
    is_active: bool
    version: int
    deactivated_at: datetime | None = None
    deactivation_reason: str | None = None


# --- discounts & credit -----------------------------------------------------------------------------------------
class DiscountIn(BaseModel):
    customer_id: uuid.UUID
    percent: Percent
    effective_from: date
    effective_to: date | None = None
    reason: Reason
    reason_code_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _dates(self) -> "DiscountIn":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not be before effective_from")
        return self


class DiscountUpdateIn(BaseModel):
    percent: Percent
    effective_from: date
    effective_to: date | None = None
    reason: Reason
    reason_code_id: uuid.UUID | None = None
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def _dates(self) -> "DiscountUpdateIn":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not be before effective_from")
        return self


class DiscountDto(Dto):
    id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str | None = None
    percent: Decimal
    effective_from: date
    effective_to: date | None
    reason: str
    reason_code_id: uuid.UUID | None
    status: ProposalStatus
    proposed_by: uuid.UUID | None
    proposed_by_name: str | None = None
    proposed_at: datetime
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None
    revoked_by: uuid.UUID | None
    revoked_by_name: str | None = None
    revoked_at: datetime | None
    revoke_reason: str | None
    version: int


class CreditArrangementIn(BaseModel):
    customer_id: uuid.UUID
    limit_amount: PositiveAmount
    currency: CurrencyCode | None = Field(default=None, description="Defaults to the tenant currency")
    effective_from: date
    effective_to: date | None = None
    terms: Note | None = None
    reason: Reason
    reason_code_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _dates(self) -> "CreditArrangementIn":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not be before effective_from")
        return self


class CreditArrangementUpdateIn(BaseModel):
    limit_amount: PositiveAmount
    effective_from: date
    effective_to: date | None = None
    terms: Note | None = None
    reason: Reason
    reason_code_id: uuid.UUID | None = None
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def _dates(self) -> "CreditArrangementUpdateIn":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must not be before effective_from")
        return self


class CreditArrangementDto(Dto):
    id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str | None = None
    limit_amount: Money
    currency: str
    effective_from: date
    effective_to: date | None
    terms: str | None
    reason: str
    reason_code_id: uuid.UUID | None
    status: ProposalStatus
    proposed_by: uuid.UUID | None
    proposed_by_name: str | None = None
    proposed_at: datetime
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None
    revoked_by: uuid.UUID | None
    revoked_by_name: str | None = None
    revoked_at: datetime | None
    revoke_reason: str | None
    version: int


class CreditExposureDto(BaseModel):
    """Credit-activated value not yet covered by verified payments, against the approved limit in effect."""

    customer_id: uuid.UUID
    currency: str
    arrangement_id: uuid.UUID | None
    limit_amount: Money | None
    exposure: Money
    available: Money | None


# --- purchases --------------------------------------------------------------------------------------------------
class PurchasePaymentIn(BaseModel):
    """Money taken together with the purchase. It is recorded as a CLAIMED customer payment (cash enters the
    custodian's custody) and linked to the purchase; hours activate only when someone else verifies it."""

    amount: PositiveAmount | None = Field(default=None, description="Defaults to the purchase amount")
    method: HirePaymentMethod
    reference: Ref | None = Field(default=None, description="Required for BANK and MOBILE_MONEY")
    received_at: datetime
    staff_member_id: uuid.UUID | None = Field(
        default=None, description="Cash custodian (defaults to the caller's staff record for CASH)"
    )
    note: Note | None = None
    evidence_attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _reference(self) -> "PurchasePaymentIn":
        if self.method is not HirePaymentMethod.CASH and not self.reference:
            raise ValueError("reference is required for BANK and MOBILE_MONEY payments")
        return self


class HoursPurchaseIn(BaseModel):
    customer_id: uuid.UUID | None = Field(default=None, description="Give customer_id or walk_in, not both")
    walk_in: WalkInCustomerIn | None = None
    machine_id: uuid.UUID = Field(description="The specific machine the hours are for")
    hours: PositiveHours
    job_site_id: uuid.UUID | None = None
    note: Note | None = None
    client_id: uuid.UUID | None = Field(default=None, description="Device/client id (offline idempotency)")
    payment: PurchasePaymentIn | None = None

    @model_validator(mode="after")
    def _customer(self) -> "HoursPurchaseIn":
        if (self.customer_id is None) == (self.walk_in is None):
            raise ValueError("give exactly one of customer_id or walk_in")
        return self


class PurchaseAllocationIn(BaseModel):
    payment_id: uuid.UUID
    amount: PositiveAmount


class PurchaseAllocationDto(Dto):
    id: uuid.UUID
    payment_id: uuid.UUID
    purchase_id: uuid.UUID
    amount: Money
    created_at: datetime
    released_at: datetime | None
    release_reason: str | None
    payment_status: str | None = None


class CreditActivationIn(BaseModel):
    hours: PositiveHours
    reason: Reason


class MachineHoursDto(BaseModel):
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    activated: Decimal
    transferred_in: Decimal
    consumed: Decimal
    transferred_out: Decimal
    expired: Decimal
    reversed: Decimal
    remaining: Decimal


class PurchaseTotalsDto(BaseModel):
    """All derived from the ledger: remaining = activated - consumed - expired - reversed (transfers net out)."""

    purchased: Decimal
    activated: Decimal
    activated_from_payments: Decimal
    activated_on_credit: Decimal
    awaiting_activation: Decimal
    consumed: Decimal
    transferred: Decimal
    expired: Decimal
    reversed: Decimal
    remaining: Decimal
    amount_verified: Money
    amount_claimed_unverified: Money
    amount_outstanding: Money


class HoursPurchaseDto(BaseModel):
    id: uuid.UUID
    purchase_number: str
    client_id: uuid.UUID | None
    customer_id: uuid.UUID
    customer_name: str | None = None
    customer_kind: CustomerKind | None = None
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    job_site_id: uuid.UUID | None
    job_site_name: str | None = None
    hours: Decimal
    currency: str
    rate_card_id: uuid.UUID
    hourly_rate: Money
    discount_id: uuid.UUID | None
    discount_percent: Decimal
    effective_rate: Money
    amount: Money
    note: str | None
    source: str
    policy_version: str
    created_by: uuid.UUID | None
    created_by_name: str | None = None
    created_at: datetime
    cancelled_at: datetime | None
    cancellation_id: uuid.UUID | None
    status: PurchaseStatus
    totals: PurchaseTotalsDto
    machines: list[MachineHoursDto] = []
    allocations: list[PurchaseAllocationDto] = []
    payment: CustomerPaymentDto | None = Field(default=None, description="The payment recorded with the purchase")


class LedgerEntryDto(Dto):
    id: uuid.UUID
    purchase_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str | None = None
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    entry_type: LedgerEntryType
    hours: Decimal
    signed_hours: Decimal = Decimal(0)
    occurred_at: datetime
    activation_source: ActivationSource | None
    expires_at: datetime | None
    payment_id: uuid.UUID | None
    job_id: uuid.UUID | None
    allocation_id: uuid.UUID | None
    transfer_id: uuid.UUID | None
    cancellation_id: uuid.UUID | None
    reason: str | None
    policy_version: str | None
    created_by: uuid.UUID | None
    created_at: datetime


class HoursBalanceDto(BaseModel):
    """Remaining activated hours of one customer on one machine (all of the customer's purchases)."""

    customer_id: uuid.UUID
    customer_name: str | None = None
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    purchases: int
    activated: Decimal
    transferred_in: Decimal
    consumed: Decimal
    transferred_out: Decimal
    expired: Decimal
    reversed: Decimal
    remaining: Decimal
    awaiting_activation: Decimal


# --- transfers & cancellations ----------------------------------------------------------------------------------
class TransferIn(BaseModel):
    purchase_id: uuid.UUID
    from_machine_id: uuid.UUID | None = Field(default=None, description="Defaults to the purchase's machine")
    to_machine_id: uuid.UUID
    hours: PositiveHours
    reason: Reason
    reason_code_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None


class TransferDto(Dto):
    id: uuid.UUID
    client_id: uuid.UUID | None
    purchase_id: uuid.UUID
    purchase_number: str | None = None
    customer_name: str | None = None
    from_machine_id: uuid.UUID
    from_machine_code: str | None = None
    from_machine_name: str | None = None
    to_machine_id: uuid.UUID
    to_machine_code: str | None = None
    to_machine_name: str | None = None
    hours: Decimal
    reason: str
    reason_code_id: uuid.UUID | None
    status: RequestStatus
    requested_by: uuid.UUID | None
    requested_by_name: str | None = None
    requested_at: datetime
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None


class CancellationIn(BaseModel):
    reason: Reason
    reason_code_id: uuid.UUID | None = None


class CancellationDto(Dto):
    id: uuid.UUID
    purchase_id: uuid.UUID
    purchase_number: str | None = None
    customer_name: str | None = None
    reason: str
    reason_code_id: uuid.UUID | None
    status: RequestStatus
    requested_by: uuid.UUID | None
    requested_by_name: str | None = None
    requested_at: datetime
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decided_at: datetime | None
    decision_note: str | None


# --- work execution allocation ----------------------------------------------------------------------------------
class AllocationLineDto(BaseModel):
    purchase_id: uuid.UUID
    purchase_number: str
    hours: Decimal
    entry_id: uuid.UUID
    occurred_at: datetime


class WorkExecutionAllocationDto(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_number: str | None = None
    customer_id: uuid.UUID
    customer_name: str | None = None
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    billable_hours: Decimal
    consumed_hours: Decimal
    overrun_hours: Decimal
    exception_id: uuid.UUID | None
    exception_status: str | None
    policy_version: str
    created_at: datetime
    lines: list[AllocationLineDto]


# --- payment evidence -------------------------------------------------------------------------------------------
class EvidenceLinkIn(BaseModel):
    attachment_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)


class PaymentEvidenceDto(Dto):
    id: uuid.UUID
    payment_id: uuid.UUID
    attachment_id: uuid.UUID
    created_by: uuid.UUID | None
    created_at: datetime
