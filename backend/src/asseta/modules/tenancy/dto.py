import uuid
from datetime import date, datetime
from typing import Annotated
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from asseta.modules.platform_billing.dto import CurrencyCode, RateTermsIn
from asseta.modules.tenancy.models import TenantAccessState, TenantStatus, VerificationStatus

Name = Annotated[str, StringConstraints(min_length=2, max_length=200, strip_whitespace=True)]


class OwnerIn(BaseModel):
    email: EmailStr
    first_name: Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]
    last_name: Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]


class SubscriptionSetupIn(BaseModel):
    start_date: date
    trial_days: int = Field(default=0, ge=0, le=365)
    payment_terms_days: int = Field(default=14, ge=0, le=180)
    signed_reference: str | None = Field(default=None, max_length=200)
    rate: RateTermsIn


class TenantOnboardIn(BaseModel):
    legal_name: Name
    display_name: Annotated[str, StringConstraints(min_length=2, max_length=120, strip_whitespace=True)]
    registration_number: str | None = Field(default=None, max_length=64)
    contact_name: Name
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=40)
    timezone: str
    currency: CurrencyCode
    locale: str = Field(default="en", max_length=16)
    owner: OwnerIn
    subscription: SubscriptionSetupIn

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        if v not in available_timezones():
            raise ValueError("unknown IANA timezone")
        return v


class TenantDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    legal_name: str
    display_name: str
    registration_number: str | None
    verification_status: VerificationStatus
    contact_name: str
    contact_email: str
    contact_phone: str | None
    status: TenantStatus
    access_state: TenantAccessState
    access_state_reason: str | None
    created_at: datetime
    version: int = 1


class TenantUpdateIn(BaseModel):
    """Company details only. Billing currency and timezone are fixed after onboarding (invoices, billing calendars
    and policy dates depend on them); lifecycle (suspend/cancel) goes through subscription transitions."""

    legal_name: Name
    display_name: Annotated[str, StringConstraints(min_length=2, max_length=120, strip_whitespace=True)]
    registration_number: str | None = Field(
        default=None, max_length=64, description="Fixed once the company is VERIFIED (reject verification first)"
    )
    contact_name: Name
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=40)
    version: int = Field(ge=1, description="Optimistic concurrency token from the last read")


class OnboardResultDto(BaseModel):
    tenant: TenantDto
    subscription_id: uuid.UUID
    owner_email: str
    owner_temporary_password: str = Field(description="Shown once; owner must change it at first login")


class VerificationIn(BaseModel):
    status: VerificationStatus
    note: Annotated[str, StringConstraints(min_length=3, max_length=1000)]
