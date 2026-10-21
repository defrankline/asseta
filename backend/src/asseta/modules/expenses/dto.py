"""Expense, fuel and approval DTOs."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from asseta.modules.expenses.models import ApprovalStatus, ExpensePaidFrom, ExpenseStatus, FuelEventType
from asseta.modules.meter.dto import GpsIn
from asseta.modules.platform_billing.dto import CurrencyCode, Money

PositiveAmount = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]
Text200 = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ExpenseCategoryIn(BaseModel):
    code: Annotated[str, StringConstraints(min_length=1, max_length=32, strip_whitespace=True)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=120, strip_whitespace=True)]


class ExpenseCategoryDto(Dto):
    id: uuid.UUID
    code: str
    name: str
    is_active: bool
    sync_revision: int
    version: int = 1
    deactivated_at: datetime | None = None
    deactivation_reason: str | None = None


class ExpenseCategoryUpdateIn(ExpenseCategoryIn):
    version: int = Field(ge=1, description="Optimistic concurrency token from the last read")


class ExpenseIn(BaseModel):
    client_id: uuid.UUID | None = Field(default=None, description="Device-generated id (offline idempotency)")
    category_id: uuid.UUID
    supplier: Text200 | None = None
    description: Annotated[str, StringConstraints(min_length=1, max_length=2000, strip_whitespace=True)]
    amount: PositiveAmount
    currency: CurrencyCode | None = Field(default=None, description="Defaults to the tenant currency")
    incurred_at: datetime
    machine_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = Field(default=None, description="Attributes the cost to a job (and its machine)")
    paid_from: ExpensePaidFrom
    custodian_staff_id: uuid.UUID | None = Field(
        default=None, description="Whose cash custody paid (CASH_CUSTODY); defaults to the caller's staff record"
    )
    receipt_attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    gps: GpsIn | None = None
    device_id: str | None = Field(default=None, max_length=128)


class ExpenseDto(Dto):
    id: uuid.UUID
    client_id: uuid.UUID | None
    category_id: uuid.UUID
    supplier: str | None
    description: str
    amount: Money
    currency: str
    incurred_at: datetime
    machine_id: uuid.UUID | None
    job_id: uuid.UUID | None
    paid_from: ExpensePaidFrom
    custodian_staff_id: uuid.UUID | None
    status: ExpenseStatus
    policy_version: str
    receipt_required: bool
    gps_status: str | None
    latitude: float | None
    longitude: float | None
    gps_accuracy_m: float | None
    source: str
    submitted_by: uuid.UUID | None
    submitted_at: datetime
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    decision_note: str | None
    receipt_attachment_ids: list[uuid.UUID] = []
    approval_request_id: uuid.UUID | None = None


class FuelEventIn(BaseModel):
    client_id: uuid.UUID | None = None
    event_type: FuelEventType
    litres: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3)]
    unit_price: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)] | None = None
    currency: CurrencyCode | None = None
    machine_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    expense_id: uuid.UUID | None = Field(default=None, description="The expense that paid for this PURCHASE")
    meter_reading: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)] | None = None
    supplier: Text200 | None = None
    occurred_at: datetime
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _shape(self) -> "FuelEventIn":
        if self.event_type is not FuelEventType.PURCHASE and self.machine_id is None and self.job_id is None:
            raise ValueError("ISSUE and USAGE events need machine_id or job_id")
        if self.event_type is not FuelEventType.USAGE and self.unit_price is None:
            raise ValueError("PURCHASE and ISSUE events need unit_price")
        if self.event_type is not FuelEventType.PURCHASE and self.expense_id is not None:
            raise ValueError("only PURCHASE events link to an expense")
        return self


class FuelEventDto(Dto):
    id: uuid.UUID
    client_id: uuid.UUID | None
    event_type: FuelEventType
    litres: Decimal
    unit_price: Money | None
    attributed_cost: Money
    currency: str
    machine_id: uuid.UUID | None
    job_id: uuid.UUID | None
    expense_id: uuid.UUID | None
    meter_reading: Decimal | None
    supplier: str | None
    occurred_at: datetime
    note: str | None
    source: str
    recorded_by: uuid.UUID | None


class ApprovalRequestDto(Dto):
    id: uuid.UUID
    subject_type: str
    subject_id: uuid.UUID
    amount: Money
    currency: str
    reason: str
    policy_version: str
    status: ApprovalStatus
    requested_by: uuid.UUID | None
    requested_at: datetime
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    decision_note: str | None


class ApprovalDecisionIn(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=1000)
