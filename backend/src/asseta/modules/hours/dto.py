"""Customer hours DTOs. Hours and money are decimal strings; every amount carries its currency."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from asseta.modules.customers.models import CustomerKind
from asseta.modules.finance.dto import CustomerPaymentDto
from asseta.modules.finance.models import HirePaymentMethod
from asseta.modules.hours.models import (
    ActivationSource,
    LedgerEntryType,
    ProposalStatus,
    ReasonKind,
    RequestStatus,
)
from asseta.modules.platform_billing.dto import CurrencyCode, Money, Reason

PositiveHours = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
PositiveAmount = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]
Percent = Annotated[Decimal, Field(gt=0, le=100, max_digits=7, decimal_places=4)]
Note = Annotated[str, StringConstraints(max_length=1000, strip_whitespace=True)]
Ref = Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
Code = Annotated[str, StringConstraints(min_length=1, max_length=32, strip_whitespace=True)]
Phone = Annotated[str, StringConstraints(min_length=3, max_length=40, strip_whitespace=True)]
# CREDIT_REJECTED: the whole order was on credit and the credit was rejected (nothing to activate)
PurchaseStatus = Literal[
    "AWAITING_PAYMENT", "PARTLY_ACTIVE", "ACTIVE", "CONSUMED", "EXPIRED", "CANCELLED", "CREDIT_REJECTED"
]
# The CREDIT part of an order: waiting for credit approval, (partly) activated on credit or settled, or rejected
CreditPartStatus = Literal["AWAITING_ACTIVATION", "ACTIVATED", "REJECTED"]


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
    evidence_attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)

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
    evidence_attachment_ids: list[uuid.UUID] | None = Field(
        default=None, max_length=20, description="Replaces the evidence; omit to keep what is attached"
    )
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
    evidence_attachment_ids: list[uuid.UUID] | None = None


class CreditExposureDto(BaseModel):
    """Credit-activated value not yet covered by verified payments, against the approved limit in effect."""

    customer_id: uuid.UUID
    currency: str
    arrangement_id: uuid.UUID | None
    limit_amount: Money | None
    exposure: Money
    available: Money | None


# --- purchases --------------------------------------------------------------------------------------------------
class SalePaymentMethod(StrEnum):
    """A payment line of an order (ADR-008 §1). CREDIT is not money received: the customer pays it later on the
    credit invoice the sale creates."""

    CASH = "CASH"
    BANK = "BANK"
    MOBILE_MONEY = "MOBILE_MONEY"
    CREDIT = "CREDIT"


class PurchasePaymentIn(BaseModel):
    """One payment line of the order. CASH / BANK / MOBILE_MONEY: money taken with the sale, recorded as a CLAIMED
    customer payment (cash enters the custodian's custody) and linked to the purchase; hours activate once it is
    verified (or per the tenant's cash activation). CREDIT: amount only (registered customers, at most one line); it
    creates the order's credit invoice and activates nothing by itself."""

    amount: PositiveAmount | None = Field(default=None, description="Defaults to the purchase amount")
    method: SalePaymentMethod
    reference: Ref | None = Field(default=None, description="Required for BANK and MOBILE_MONEY")
    received_at: datetime | None = Field(default=None, description="Required for every method except CREDIT")
    staff_member_id: uuid.UUID | None = Field(
        default=None, description="Cash custodian (defaults to the caller's staff record for CASH)"
    )
    note: Note | None = None
    evidence_attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _reference(self) -> "PurchasePaymentIn":
        if self.method in (SalePaymentMethod.BANK, SalePaymentMethod.MOBILE_MONEY) and not self.reference:
            raise ValueError("reference is required for BANK and MOBILE_MONEY payments")
        if self.method is not SalePaymentMethod.CREDIT and self.received_at is None:
            raise ValueError("received_at is required for money received")
        return self

    @property
    def is_credit(self) -> bool:
        return self.method is SalePaymentMethod.CREDIT

    @property
    def money_method(self) -> HirePaymentMethod:
        return HirePaymentMethod(self.method.value)


class HoursPurchaseIn(BaseModel):
    customer_id: uuid.UUID | None = Field(default=None, description="Give customer_id or walk_in, not both")
    walk_in: WalkInCustomerIn | None = None
    machine_id: uuid.UUID = Field(description="The specific machine the hours are for")
    hours: PositiveHours
    job_site_id: uuid.UUID | None = None
    note: Note | None = None
    client_id: uuid.UUID | None = Field(default=None, description="Device/client id (offline idempotency)")
    client_created_at: datetime | None = Field(default=None, description="Device time the purchase was recorded")
    payment: PurchasePaymentIn | None = None
    payments: list[PurchasePaymentIn] = Field(
        default_factory=list,
        max_length=10,
        description="The bill split across methods (cash + bank + mobile money + credit); each part needs its amount. "
        "Give payment or payments, not both. Together they may not exceed the purchase amount. At most one CREDIT "
        "line (registered customers only): it creates the order's credit invoice.",
    )

    @model_validator(mode="after")
    def _customer(self) -> "HoursPurchaseIn":
        if (self.customer_id is None) == (self.walk_in is None):
            raise ValueError("give exactly one of customer_id or walk_in")
        if self.payment is not None and self.payments:
            raise ValueError("give payment or payments, not both")
        if len(self.payments) > 1 and any(p.amount is None for p in self.payments):
            raise ValueError("every part of a split payment needs its amount")
        if sum(1 for p in self.payment_parts() if p.is_credit) > 1:
            raise ValueError("at most one CREDIT line")
        return self

    def payment_parts(self) -> list[PurchasePaymentIn]:
        return [self.payment] if self.payment is not None else list(self.payments)

    def money_parts(self) -> list[PurchasePaymentIn]:
        """The lines that are money received (every line but CREDIT)."""
        return [p for p in self.payment_parts() if not p.is_credit]

    def credit_part(self) -> PurchasePaymentIn | None:
        return next((p for p in self.payment_parts() if p.is_credit), None)


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


class CreditRejectionIn(BaseModel):
    reason: Reason = Field(description="Why the credit is not approved (told to the seller)")


class CreditRejectionDto(BaseModel):
    """The credit part of an order was not approved: its hours are never activated and its invoice is CANCELLED."""

    rejected_at: datetime
    rejected_by: uuid.UUID | None
    rejected_by_name: str | None = None
    reason: str
    hours: Decimal = Field(description="The credit hours that will not be activated")
    amount: Money = Field(description="The credit amount no longer owed")


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
    refunded: Decimal = Decimal(0)
    corrected: Decimal = Decimal(0)  # net corrections on the lot
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
    refunded: Decimal = Decimal(0)
    corrected: Decimal = Decimal(0)  # net corrections on the lot
    remaining: Decimal
    amount_verified: Money
    amount_claimed_unverified: Money
    amount_outstanding: Money


class HoursQuoteDto(BaseModel):
    """What an hours sale would cost now: the rate card, less the customer's approved discount, times the hours."""

    machine_id: uuid.UUID
    customer_id: uuid.UUID | None
    hours: Decimal
    hourly_rate: Decimal
    discount_percent: Decimal
    effective_rate: Decimal
    amount: Decimal
    currency: str
    minimum_hours: Decimal


class HoursPriceDto(BaseModel):
    """A machine's current hourly rate (its type's rate card), in the sync snapshot for offline pricing."""

    machine_id: uuid.UUID
    rate_card_id: uuid.UUID
    hourly_rate: Decimal
    minimum_hours: Decimal
    currency: str
    minor_units: int = Field(description="Decimal places the total is rounded to (the server's currency setting)")
    effective_from: datetime


class CustomerDiscountRateDto(BaseModel):
    """A customer's approved discount in force today: percent off the hourly rate."""

    customer_id: uuid.UUID
    percent: Decimal


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
    client_created_at: datetime | None = None
    pending_zero_amount_request_id: uuid.UUID | None = None
    status: PurchaseStatus
    totals: PurchaseTotalsDto
    machines: list[MachineHoursDto] = []
    allocations: list[PurchaseAllocationDto] = []
    payment: CustomerPaymentDto | None = Field(default=None, description="The payment recorded with the purchase")
    payments: list[CustomerPaymentDto] = Field(
        default_factory=list, description="Every payment part recorded with the purchase (split bills)"
    )
    credit_amount: Money | None = Field(
        default=None, description="The CREDIT line of the order (paid later on its credit invoice); null without one"
    )
    credit_invoice: "CreditInvoiceSummaryDto | None" = Field(
        default=None, description="The credit invoice created for the CREDIT line"
    )
    credit_status: CreditPartStatus | None = Field(
        default=None,
        description="The CREDIT part: AWAITING_ACTIVATION (the credit approvers' queue), ACTIVATED (activated on "
        "credit or nothing left to activate) or REJECTED; null without a CREDIT line",
    )
    credit_rejection: CreditRejectionDto | None = Field(
        default=None, description="Who rejected the credit, when and why (credit_status REJECTED)"
    )


class LedgerEntryDto(Dto):
    id: uuid.UUID
    purchase_id: uuid.UUID
    purchase_number: str | None = None
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
    machine_report_id: uuid.UUID | None = Field(default=None, description="CONSUMED: the approved machine report")
    machine_report_number: str | None = None
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
    refunded: Decimal = Decimal(0)
    corrected: Decimal = Decimal(0)  # net corrections on the lot
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
    evidence_attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)


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
    transfer_number: str | None = None
    evidence_attachment_ids: list[uuid.UUID] | None = None


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


# --- payment evidence -------------------------------------------------------------------------------------------
class EvidenceLinkIn(BaseModel):
    attachment_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)


class PaymentEvidenceDto(Dto):
    id: uuid.UUID
    payment_id: uuid.UUID
    attachment_id: uuid.UUID
    created_by: uuid.UUID | None
    created_at: datetime


# --- low-balance alerts (DEC-031 P2) ----------------------------------------------------------------------------
LowBalanceSmsStatus = Literal["NOT_REQUESTED", "PENDING", "QUEUED", "NO_PHONE"]


class LowBalanceAlertDto(Dto):
    """One crossing of the tenant's low-balance threshold by a purchase (the office was told once)."""

    id: uuid.UUID
    purchase_id: uuid.UUID
    purchase_number: str | None = None
    customer_id: uuid.UUID
    customer_name: str | None = None
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    sequence: int
    threshold_hours: Decimal
    remaining_hours: Decimal
    available_hours: Decimal
    crossed_at: datetime
    notify_customer: bool
    customer_sms_status: LowBalanceSmsStatus
    customer_sms_id: uuid.UUID | None
    rearmed_at: datetime | None
    policy_version: str


# --- customer hours statement (DEC-031 P3) ----------------------------------------------------------------------
class HoursStatementTotalsDto(BaseModel):
    """Movements inside the period (hours). closing = opening + activated + transferred_in - used - transferred_out
    - expired - cancelled."""

    opening_balance: Decimal
    bought: Decimal = Field(description="Hours of purchases recorded in the period (activated once paid)")
    activated: Decimal
    used: Decimal = Field(description="Hours used: consumed by approved machine reports")
    transferred_in: Decimal
    transferred_out: Decimal
    expired: Decimal
    cancelled: Decimal = Field(description="Activated hours withdrawn by approved cancellations")
    refunded: Decimal = Field(default=Decimal(0), description="Unused hours refunded")
    corrected: Decimal = Field(default=Decimal(0), description="Net approved corrections")
    closing_balance: Decimal
    awaiting_activation: Decimal = Field(description="Hours bought but not yet paid / activated (now)")


class HoursStatementPurchaseDto(BaseModel):
    purchase_id: uuid.UUID
    purchase_number: str | None = None
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    bought_at: datetime
    hours: Decimal
    currency: CurrencyCode
    effective_rate: Money
    amount: Money
    status: PurchaseStatus
    activated: Decimal
    remaining_at_close: Decimal
    next_expiry_at: datetime | None
    expiring_hours: Decimal = Field(description="Hours that will expire at next_expiry_at unless used first")
    cancelled_at: datetime | None


class HoursStatementUsageDto(BaseModel):
    """Hours used on one day (the day the machine report was approved) on one machine report."""

    day: date
    machine_report_id: uuid.UUID | None
    machine_report_number: str | None = None
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    hours: Decimal


class HoursStatementLineDto(BaseModel):
    """One ledger movement in the period, in order, with the running balance."""

    entry_id: uuid.UUID
    day: date
    occurred_at: datetime
    entry_type: LedgerEntryType
    purchase_id: uuid.UUID
    purchase_number: str | None = None
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    machine_report_id: uuid.UUID | None = None
    machine_report_number: str | None = None
    hours: Decimal = Field(description="Signed: + adds to the balance, - takes from it")
    balance_after: Decimal
    reason: str | None


class HoursStatementDto(BaseModel):
    customer_id: uuid.UUID
    customer_name: str | None = None
    machine_id: uuid.UUID | None
    machine_code: str | None = None
    machine_name: str | None = None
    date_from: date
    date_to: date
    timezone: str
    generated_at: datetime
    totals: HoursStatementTotalsDto
    purchases: list[HoursStatementPurchaseDto]
    usage: list[HoursStatementUsageDto]
    lines: list[HoursStatementLineDto]
    pdf_path: str = Field(description="Same statement as a PDF (GET, same query)")


# --- credit invoices (ADR-008 §1) -------------------------------------------------------------------------------
CreditInvoiceStatus = Literal["UNPAID", "PART_PAID", "PAID", "CANCELLED"]
InvoicePaymentMethod = Literal["CASH", "BANK", "MOBILE_MONEY"]


class CreditInvoiceSummaryDto(BaseModel):
    """The credit invoice of an order, as shown on the order."""

    id: uuid.UUID
    invoice_number: str
    amount: Money
    paid: Money
    balance: Money
    due_date: date
    status: CreditInvoiceStatus
    overdue: bool
    rejection: CreditRejectionDto | None = Field(
        default=None, description="Set when the credit was rejected (the invoice is then CANCELLED)"
    )


class CreditInvoicePaymentDto(BaseModel):
    """One payment recorded against a credit invoice (its customer payment record carries the money's status)."""

    id: uuid.UUID
    payment_id: uuid.UUID
    amount: Money
    method: HirePaymentMethod
    reference: str | None
    collection_number: str | None = None
    payment_status: str
    received_at: datetime
    received_by_staff_id: uuid.UUID | None
    received_by_staff_name: str | None = None
    recorded_by: uuid.UUID | None
    recorded_by_name: str | None = None
    created_at: datetime
    counts: bool = Field(description="False once the payment was rejected or reversed (it no longer pays the invoice)")


class CreditInvoiceDto(BaseModel):
    """CI-<yyyy>-<nnnnn>: created automatically for the CREDIT line of an order. Paid in full or in parts (cash, bank,
    mobile money). Status: UNPAID, PART_PAID, PAID (CANCELLED when its order was cancelled or its credit rejected);
    `overdue` once the due date passed with a balance. Recorded payments count (claimed or verified) until rejected
    or reversed."""

    id: uuid.UUID
    invoice_number: str
    purchase_id: uuid.UUID
    purchase_number: str | None = None
    customer_id: uuid.UUID
    customer_name: str | None = None
    machine_id: uuid.UUID
    machine_code: str | None = None
    machine_name: str | None = None
    currency: str
    hours: Decimal = Field(description="Hours the credit amount pays for (amount / the order's effective rate)")
    unit_price: Money = Field(description="The order's effective hourly rate")
    amount: Money
    paid: Money
    paid_verified: Money = Field(description="Of `paid`: money already verified")
    balance: Money
    payment_terms_days: int
    issued_at: datetime
    due_date: date
    status: CreditInvoiceStatus
    overdue: bool
    days_overdue: int
    created_by: uuid.UUID | None
    created_by_name: str | None = None
    rejection: CreditRejectionDto | None = Field(
        default=None, description="Set when the credit was rejected (the invoice is then CANCELLED, balance 0)"
    )
    payments: list[CreditInvoicePaymentDto] = []


class CreditInvoicePaymentIn(BaseModel):
    """A payment (in full or part) of a credit invoice. CASH goes into the recorder's (or the named custodian's) cash
    custody like any collection; BANK and MOBILE_MONEY need the transaction reference and stay claimed until the
    office verifies them. Field staff record bank / mobile money only when the tenant allows field non-cash payments."""

    client_id: uuid.UUID | None = Field(default=None, description="Device/client id (offline idempotency)")
    amount: PositiveAmount = Field(description="At most the invoice balance")
    method: InvoicePaymentMethod
    reference: Ref | None = Field(default=None, description="Required for BANK and MOBILE_MONEY")
    received_at: datetime
    staff_member_id: uuid.UUID | None = Field(
        default=None, description="Cash custodian (defaults to the caller's staff record for CASH)"
    )
    note: Note | None = None
    evidence_attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _reference(self) -> "CreditInvoicePaymentIn":
        if self.method != "CASH" and not self.reference:
            raise ValueError("reference is required for BANK and MOBILE_MONEY payments")
        return self


class CustomerHoursSummaryDto(BaseModel):
    """One customer's hours (ADR-008): bought (orders not cancelled), activated, used (approved machine reports and
    any older consumption), left to use, still awaiting payment or activation, and credit still owed."""

    customer_id: uuid.UUID
    customer_name: str | None = None
    bought: Decimal
    activated: Decimal
    used: Decimal
    left: Decimal
    awaiting_activation: Decimal
    credit_owed: Money = Field(description="Balance of the customer's open credit invoices (tenant currency)")


HoursPurchaseDto.model_rebuild()
