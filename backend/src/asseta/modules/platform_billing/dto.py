"""Platform billing DTOs (requests and responses). Money is serialized as decimal strings."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints

from asseta.core.money import RoundingMode
from asseta.modules.platform_billing.enums import (
    Cadence,
    EnrollmentEndReason,
    InvoiceLineType,
    InvoiceStatus,
    MidCycleAddPolicy,
    MidCycleRemovePolicy,
    PaymentMethod,
    PaymentStatus,
    PendingChargeStatus,
    SubscriptionStatus,
)

MONEY_SCALE = Decimal("0.0001")  # storage scale; clients format to currency.minor_units for display
Money = Annotated[
    Decimal, PlainSerializer(lambda v: format(v.quantize(MONEY_SCALE), "f"), return_type=str, when_used="json")
]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
Reason = Annotated[str, StringConstraints(min_length=3, max_length=1000, strip_whitespace=True)]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RateTermsIn(BaseModel):
    """Negotiated per-asset price for the cadence period (e.g. per machine per month)."""

    currency: CurrencyCode
    cadence: Cadence
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    minimum_billable_assets: int = Field(ge=1)
    discount_percent: Decimal = Field(default=Decimal(0), ge=0, le=100, decimal_places=4)
    tax_name: str | None = Field(default=None, max_length=40)
    tax_rate_percent: Decimal = Field(default=Decimal(0), ge=0, le=100, decimal_places=4)
    mid_cycle_add: MidCycleAddPolicy = MidCycleAddPolicy.PRORATE_DAILY
    mid_cycle_remove: MidCycleRemovePolicy = MidCycleRemovePolicy.PRORATE_CREDIT
    rounding_mode: RoundingMode = RoundingMode.HALF_UP


class NewRateVersionIn(RateTermsIn):
    effective_from: date
    reason: Reason


class RateVersionDto(Dto):
    id: uuid.UUID
    version: int
    effective_from: date
    currency: str
    cadence: Cadence
    unit_price: Money
    minimum_billable_assets: int
    discount_percent: Money
    tax_name: str | None
    tax_rate_percent: Money
    mid_cycle_add: MidCycleAddPolicy
    mid_cycle_remove: MidCycleRemovePolicy
    rounding_mode: RoundingMode
    reason: str
    created_at: datetime


class SubscriptionDto(Dto):
    id: uuid.UUID
    tenant_id: uuid.UUID
    agreement_id: uuid.UUID
    agreement_number: str
    status: SubscriptionStatus
    start_date: date
    billing_start_date: date
    billing_anchor_day: int
    cancellation_effective_date: date | None
    manually_suspended: bool
    payment_terms_days: int
    current_rate: RateVersionDto | None
    current_period_start: date | None
    current_period_end: date | None
    enrolled_assets: int
    billable_assets: int


class TransitionIn(BaseModel):
    to_status: SubscriptionStatus
    effective_date: date
    reason: Reason


class EnrollAssetIn(BaseModel):
    machine_id: uuid.UUID
    effective_from: date


class EndEnrollmentIn(BaseModel):
    effective_to: date
    reason: EnrollmentEndReason


class ChargePreviewDto(BaseModel):
    line_type: InvoiceLineType
    service_from: date | None
    service_to: date | None
    days: int
    period_days: int
    amount: Money
    currency: str
    explanation: str


class EnrollmentDto(Dto):
    id: uuid.UUID
    machine_id: uuid.UUID
    asset_label: str
    effective_from: date
    effective_to: date | None
    end_reason: EnrollmentEndReason | None


class EnrollmentResultDto(BaseModel):
    enrollment: EnrollmentDto
    charge: ChargePreviewDto | None


class PendingChargeDto(Dto):
    id: uuid.UUID
    enrollment_id: uuid.UUID
    line_type: InvoiceLineType
    service_from: date
    service_to: date
    days: int
    period_days: int
    computed_amount: Money
    amount: Money
    explanation: str
    override_reason: str | None
    status: PendingChargeStatus


class OverridePendingChargeIn(BaseModel):
    amount: Decimal = Field(max_digits=18, decimal_places=4)
    reason: Reason


class InvoiceLineDto(Dto):
    line_no: int
    line_type: InvoiceLineType
    machine_id: uuid.UUID | None
    description: str
    quantity: Decimal
    unit_price: Money
    amount: Money
    service_from: date | None
    service_to: date | None


class InvoiceDto(Dto):
    id: uuid.UUID | None
    tenant_id: uuid.UUID
    invoice_number: str | None
    period_start: date
    period_end: date
    currency: str
    enrolled_assets: int
    billable_assets: int
    subtotal: Money
    discount_total: Money
    tax_total: Money
    total: Money
    amount_paid: Money
    credits_applied: Money
    balance: Money
    status: InvoiceStatus | None
    due_date: date
    issued_at: datetime | None
    lines: list[InvoiceLineDto]


class GenerateInvoicesIn(BaseModel):
    as_of: date


class GenerateInvoicesDto(BaseModel):
    created: list[InvoiceDto]
    existing_periods: list[date]


class RecordPaymentIn(BaseModel):
    invoice_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    currency: CurrencyCode
    method: PaymentMethod
    reference: Annotated[str, StringConstraints(min_length=2, max_length=120, strip_whitespace=True)]
    received_on: date


class PaymentDecisionIn(BaseModel):
    verified: bool
    note: Reason


class PaymentDto(Dto):
    id: uuid.UUID
    tenant_id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Money
    currency: str
    method: PaymentMethod
    reference: str
    received_on: date
    status: PaymentStatus
    recorded_at: datetime
    decided_at: datetime | None
    decision_note: str | None


class CreditAdjustmentIn(BaseModel):
    invoice_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    reason: Reason


class EntitlementDto(BaseModel):
    tenant_id: uuid.UUID
    subscription_status: SubscriptionStatus
    access_state: str
    reason: str
    policy_version: int
    changed: bool
