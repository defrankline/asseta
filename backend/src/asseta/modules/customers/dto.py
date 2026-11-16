import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from asseta.modules.customers.models import CustomerKind
from asseta.modules.platform_billing.dto import Money

Code = Annotated[str, StringConstraints(min_length=1, max_length=32, strip_whitespace=True)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]
Hours = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
Version = Annotated[int, Field(ge=1, description="Optimistic concurrency token from the last read")]


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CustomerIn(BaseModel):
    code: Code | None = Field(
        default=None,
        description="Optional; unique per company. Left blank, the server assigns CUST-<nnnnn> (on edit: kept).",
    )
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
    kind: CustomerKind = CustomerKind.REGISTERED
    is_active: bool
    version: int = 1
    deactivated_at: datetime | None = None
    deactivation_reason: str | None = None


class CustomerUpdateIn(CustomerIn):
    version: Version


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
