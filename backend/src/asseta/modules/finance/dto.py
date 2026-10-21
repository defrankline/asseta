"""Tenant hire finance DTOs. Money is serialized as decimal strings; every amount carries its currency."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from asseta.modules.finance.models import (
    CustodyEntryType,
    HireInvoiceStatus,
    HirePaymentMethod,
    SettlementStatus,
)
from asseta.modules.jobs.charges import ChargeKind
from asseta.modules.platform_billing.dto import CurrencyCode, Money, Reason

PositiveAmount = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]
Note = Annotated[str, StringConstraints(max_length=1000, strip_whitespace=True)]
Ref = Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- invoices -----------------------------------------------------------------------------------------------
class HireInvoiceDraftIn(BaseModel):
    customer_id: uuid.UUID
    job_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    notes: Note | None = None


class HireInvoiceIssueIn(BaseModel):
    due_date: date | None = Field(default=None, description="Defaults to issue date + customer payment terms")


class HireInvoiceVoidIn(BaseModel):
    reason: Reason


class HireInvoiceLineDto(Dto):
    line_no: int
    kind: ChargeKind
    job_id: uuid.UUID
    machine_id: uuid.UUID
    description: str
    quantity: Decimal
    unit_price: Money
    amount: Money


class HireInvoiceDto(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    invoice_number: str | None
    status: HireInvoiceStatus
    currency: str
    subtotal: Money
    discount_total: Money
    tax_total: Money
    total: Money
    amount_paid: Money  # verified allocations only
    balance: Money
    payment_state: Literal["UNPAID", "PARTIALLY_PAID", "PAID"] | None  # None unless ISSUED
    due_date: date | None
    notes: str | None
    created_at: datetime
    issued_at: datetime | None
    voided_at: datetime | None
    void_reason: str | None
    job_ids: list[uuid.UUID]
    lines: list[HireInvoiceLineDto]


# --- customer payments --------------------------------------------------------------------------------------
class HireAllocationIn(BaseModel):
    invoice_id: uuid.UUID
    amount: PositiveAmount


class HireAllocateIn(BaseModel):
    allocations: list[HireAllocationIn] = Field(min_length=1, max_length=50)


class CustomerPaymentIn(BaseModel):
    customer_id: uuid.UUID
    amount: PositiveAmount
    currency: CurrencyCode | None = Field(default=None, description="Defaults to the tenant currency")
    method: HirePaymentMethod
    reference: Ref | None = Field(default=None, description="Required for BANK and MOBILE_MONEY")
    received_at: datetime
    received_by_staff_id: uuid.UUID | None = None
    note: Note | None = None
    client_id: uuid.UUID | None = Field(default=None, description="Device/client id (offline idempotency)")
    allocations: list[HireAllocationIn] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _reference(self) -> "CustomerPaymentIn":
        if self.method is not HirePaymentMethod.CASH and not self.reference:
            raise ValueError("reference is required for BANK and MOBILE_MONEY payments")
        return self


class CashCollectionIn(BaseModel):
    """Cash a supervisor received from a customer (enters that supervisor's custody)."""

    client_id: uuid.UUID | None = None
    customer_id: uuid.UUID
    amount: PositiveAmount
    currency: CurrencyCode | None = None
    received_at: datetime
    staff_member_id: uuid.UUID | None = Field(default=None, description="Defaults to the caller's staff record")
    reference: Ref | None = None
    note: Note | None = None
    allocations: list[HireAllocationIn] = Field(default_factory=list, max_length=50)


class HireAllocationDto(Dto):
    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Money
    created_at: datetime
    released_at: datetime | None
    release_reason: str | None


class CustomerPaymentDto(Dto):
    id: uuid.UUID
    customer_id: uuid.UUID
    client_id: uuid.UUID | None
    amount: Money
    currency: str
    method: HirePaymentMethod
    reference: str | None
    received_at: datetime
    received_by_staff_id: uuid.UUID | None
    status: SettlementStatus
    note: str | None
    source: str
    recorded_by: uuid.UUID | None
    recorded_at: datetime
    verified_by: uuid.UUID | None
    verified_at: datetime | None
    decision_note: str | None
    allocations: list[HireAllocationDto] = []


class SettlementDecisionIn(BaseModel):
    verified: bool
    note: Note | None = None


class CustomerBalanceDto(BaseModel):
    """Positive balance = customer owes; negative = customer credit (deposits/advances/overpayment)."""

    customer_id: uuid.UUID
    currency: str
    invoiced: Money
    reversed: Money
    verified_payments: Money
    balance: Money
    unallocated_credit: Money
    claimed_unverified: Money  # shown separately; never reduces the balance
    open_invoices: int


class StatementLineDto(BaseModel):
    at: datetime
    kind: Literal["INVOICE", "REVERSAL", "PAYMENT"]
    reference: str
    description: str
    debit: Money
    credit: Money
    running_balance: Money


class CustomerStatementDto(BaseModel):
    customer_id: uuid.UUID
    currency: str
    period_from: date
    period_to: date  # inclusive, tenant local dates
    opening_balance: Money
    lines: list[StatementLineDto]
    total_debits: Money
    total_credits: Money
    closing_balance: Money
    claimed_unverified: list[CustomerPaymentDto]
    claimed_unverified_total: Money


# --- supervisor cash custody --------------------------------------------------------------------------------
class CashFloatIn(BaseModel):
    staff_member_id: uuid.UUID
    amount: PositiveAmount
    currency: CurrencyCode | None = None
    entry_type: CustodyEntryType = CustodyEntryType.FLOAT_ISSUED
    occurred_at: datetime | None = None
    reference: Ref | None = None
    note: Note | None = None


class CashCustodyEntryDto(Dto):
    id: uuid.UUID
    staff_member_id: uuid.UUID
    entry_type: CustodyEntryType
    amount: Money
    currency: str
    occurred_at: datetime
    reference: str | None
    note: str | None


class CashHandoverIn(BaseModel):
    client_id: uuid.UUID | None = None
    staff_member_id: uuid.UUID | None = Field(default=None, description="Defaults to the caller's staff record")
    amount: PositiveAmount
    currency: CurrencyCode | None = None
    handed_at: datetime
    reference: Ref | None = None
    note: Note | None = None


class CashHandoverDto(Dto):
    id: uuid.UUID
    client_id: uuid.UUID | None
    staff_member_id: uuid.UUID
    amount: Money
    currency: str
    handed_at: datetime
    reference: str | None
    note: str | None
    status: SettlementStatus
    source: str
    recorded_by: uuid.UUID | None
    recorded_at: datetime
    verified_by: uuid.UUID | None
    verified_at: datetime | None
    decision_note: str | None


class CashReconciliationDayDto(BaseModel):
    """outstanding = opening + floats_issued + collections - approved_spending - verified_handovers."""

    day: date
    opening: Money
    floats_issued: Money
    collections: Money  # claimed or verified (rejected collections excluded)
    approved_spending: Money  # APPROVED expenses paid from this custody
    verified_handovers: Money
    outstanding: Money
    claimed_unverified_handovers: Money  # shown separately; not deducted until verified
    pending_spending: Money  # expenses awaiting approval; not deducted
    unverified_collections: Money  # part of `collections` not yet verified by the office
    outstanding_if_claims_verified: Money


class CashReconciliationDto(BaseModel):
    staff_member_id: uuid.UUID
    currency: str
    timezone: str
    days: list[CashReconciliationDayDto]


class CashCustodyBalanceDto(BaseModel):
    staff_member_id: uuid.UUID
    currency: str
    outstanding: Money
    claimed_unverified_handovers: Money
    pending_spending: Money
    as_of: datetime


# --- profitability ------------------------------------------------------------------------------------------
class ProfitabilityRowDto(BaseModel):
    group_key: uuid.UUID | None  # None = costs not attributable to this grouping
    label: str
    currency: str
    revenue: Money  # issued invoice lines excl. tax, net of discounts
    reversed_revenue: Money  # voided in the period
    net_revenue: Money
    expense_cost: Money
    fuel_cost: Money
    direct_cost: Money
    margin: Money
    cost_by_category: dict[str, Money]


class ProfitabilityDto(BaseModel):
    group_by: Literal["MACHINE", "JOB", "CUSTOMER"]
    period_from: date
    period_to: date
    timezone: str
    rows: list[ProfitabilityRowDto]
