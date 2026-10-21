import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from asseta.modules.jobs.models import ActivityType, ContractStatus, JobStatus, StandbyTreatment
from asseta.modules.platform_billing.dto import Money

Code = Annotated[str, StringConstraints(min_length=1, max_length=32, strip_whitespace=True)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
Hours = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CustomerIn(BaseModel):
    code: Code
    name: Name
    tax_id: str | None = Field(default=None, max_length=64)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=40)
    contact_email: str | None = Field(default=None, max_length=320)
    payment_terms_days: int = Field(default=30, ge=0, le=365)


class CustomerDto(Dto):
    id: uuid.UUID
    code: str
    name: str
    tax_id: str | None
    contact_name: str | None
    contact_phone: str | None
    contact_email: str | None
    payment_terms_days: int
    is_active: bool


class RateCardIn(BaseModel):
    machine_category_id: uuid.UUID
    hourly_rate: Amount
    minimum_hours: Hours
    effective_from: datetime | None = None
    reason: str = Field(min_length=3, max_length=500)


class RateCardDto(Dto):
    id: uuid.UUID
    machine_category_id: uuid.UUID
    effective_from: datetime
    hourly_rate: Money
    minimum_hours: Decimal
    currency: str
    reason: str


class ContractIn(BaseModel):
    customer_id: uuid.UUID
    contract_number: Code
    job_site_id: uuid.UUID | None = None
    starts_on: datetime
    ends_on: datetime | None = None
    reference: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)


class ContractDto(Dto):
    id: uuid.UUID
    customer_id: uuid.UUID
    contract_number: str
    job_site_id: uuid.UUID | None
    currency: str
    status: ContractStatus
    starts_on: datetime
    ends_on: datetime | None
    reference: str | None


class JobIn(BaseModel):
    contract_id: uuid.UUID
    job_number: Code
    machine_id: uuid.UUID
    job_site_id: uuid.UUID | None = None
    supervisor_id: uuid.UUID | None = None
    planned_start: datetime
    planned_end: datetime | None = None
    hourly_rate: Amount | None = Field(default=None, description="Omit to use the tenant rate card")
    minimum_hours: Hours | None = None
    standby_treatment: StandbyTreatment = StandbyTreatment.EXCLUDED
    standby_rate: Amount | None = None
    mobilization_fee: Amount = Decimal(0)
    discount_percent: Annotated[Decimal, Field(ge=0, le=100)] = Decimal(0)
    tax_rate_percent: Annotated[Decimal, Field(ge=0, le=100)] = Decimal(0)

    @model_validator(mode="after")
    def _standby(self) -> "JobIn":
        if (self.standby_treatment is StandbyTreatment.STANDBY_RATE) != (self.standby_rate is not None):
            raise ValueError("standby_rate is required exactly when standby_treatment is STANDBY_RATE")
        return self


class JobDto(Dto):
    id: uuid.UUID
    contract_id: uuid.UUID
    job_number: str
    machine_id: uuid.UUID
    job_site_id: uuid.UUID | None
    supervisor_id: uuid.UUID | None
    status: JobStatus
    planned_start: datetime
    planned_end: datetime | None
    currency: str
    hourly_rate: Money
    minimum_hours: Decimal
    standby_treatment: StandbyTreatment
    standby_rate: Money | None
    mobilization_fee: Money
    discount_percent: Decimal
    tax_rate_percent: Decimal
    rate_source: str
    approved_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    version: int


class JobTransitionIn(BaseModel):
    action: Literal["SUBMIT", "APPROVE", "START", "COMPLETE", "CANCEL"]
    reason: str | None = Field(default=None, max_length=1000)


class ActivityIn(BaseModel):
    client_id: uuid.UUID
    activity_type: ActivityType
    started_at: datetime
    ended_at: datetime | None = None
    billable: bool | None = Field(default=None, description="Defaults from type and job standby terms")
    note: str | None = Field(default=None, max_length=2000)
    device_id: str | None = Field(default=None, max_length=128)


class ActivityDto(Dto):
    id: uuid.UUID
    client_id: uuid.UUID
    activity_type: ActivityType
    started_at: datetime
    ended_at: datetime | None
    billable: bool
    note: str | None


class AcknowledgementIn(BaseModel):
    client_id: uuid.UUID
    method: Literal["SIGNATURE", "NAME_CONFIRMATION"]
    signer_name: Name
    signer_phone: str | None = Field(default=None, max_length=40)
    signature_attachment_id: uuid.UUID | None = None
    acknowledged_hours: Hours | None = None
    captured_at: datetime

    @model_validator(mode="after")
    def _signature(self) -> "AcknowledgementIn":
        if self.method == "SIGNATURE" and self.signature_attachment_id is None:
            raise ValueError("SIGNATURE requires signature_attachment_id")
        return self


class AcknowledgementDto(Dto):
    id: uuid.UUID
    method: str
    signer_name: str
    acknowledged_hours: Decimal | None
    captured_at: datetime


class JobSummaryDto(BaseModel):
    job: JobDto
    opening_reading: Decimal | None
    closing_reading: Decimal | None
    meter_hours: Decimal | None  # closing - opening (engine/meter hours)
    nonbillable_hours: Decimal
    billable_hours: Decimal | None  # contract rules applied — NOT equal to meter hours
    open_exceptions: int
    blocking_exceptions: int
    billing_ready: bool
    policy_version: str
