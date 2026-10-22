"""DTOs for DEC-022 platform commerce: catalog, ad-hoc invoices, per-line allocation, SMS wallet."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from asseta.modules.platform_billing.dto import CurrencyCode, Dto, LineAllocationIn, Money, Reason
from asseta.modules.platform_billing.enums import ProductType, SmsWalletEntryType

ProductCode = Annotated[str, StringConstraints(pattern=r"^[A-Z0-9][A-Z0-9_-]{1,39}$")]
Price = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]


class ProductFieldsIn(BaseModel):
    name: Annotated[str, StringConstraints(min_length=2, max_length=200, strip_whitespace=True)]
    description: str | None = Field(default=None, max_length=2000)
    sms_credits: int | None = Field(default=None, ge=1, le=10_000_000, description="SMS_BUNDLE: credits per unit")
    prices: dict[CurrencyCode, Price] = Field(default_factory=dict, description="List price per currency")
    taxable: bool = True


class ProductIn(ProductFieldsIn):
    code: ProductCode
    product_type: ProductType


class ProductUpdateIn(ProductFieldsIn):
    version: int = Field(ge=1, description="Optimistic concurrency token from the last read")


class ProductDto(Dto):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    product_type: ProductType
    sms_credits: int | None
    prices: dict[str, Money]
    taxable: bool
    is_active: bool
    deactivated_at: datetime | None
    deactivation_reason: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class AdHocLineIn(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(default=Decimal(1), gt=0, max_digits=18, decimal_places=6)
    unit_price: Price | None = Field(default=None, description="Negotiated unit price (default: catalog price)")
    discount_percent: Decimal = Field(default=Decimal(0), ge=0, le=100, decimal_places=4)
    description: str | None = Field(default=None, max_length=300)
    period_start: date | None = Field(default=None, description="SUBSCRIPTION_FEE: start of the billed period")


class AdHocInvoiceIn(BaseModel):
    tenant_id: uuid.UUID
    currency: CurrencyCode | None = Field(default=None, description="Default: the tenant's subscription currency")
    due_date: date | None = Field(default=None, description="Default: today + agreement payment terms")
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[AdHocLineIn] = Field(min_length=1, max_length=50)


class VoidInvoiceIn(BaseModel):
    reason: Reason


class AllocatePaymentIn(BaseModel):
    allocations: list[LineAllocationIn] | None = Field(
        default=None, description="Explicit per-line allocation; omitted = oldest open invoice first, line order"
    )

    @model_validator(mode="after")
    def _distinct(self) -> "AllocatePaymentIn":
        ids = [a.line_id for a in self.allocations or []]
        if len(ids) != len(set(ids)):
            raise ValueError("Each line may appear once")
        return self


class SmsWalletEntryDto(Dto):
    id: uuid.UUID
    entry_type: SmsWalletEntryType
    credits: int
    balance_after: int
    reference_type: str
    reference_id: uuid.UUID
    note: str | None
    created_at: datetime


class SmsWalletDto(BaseModel):
    tenant_id: uuid.UUID
    balance: int
    low_balance_threshold: int
    recent_entries: list[SmsWalletEntryDto]
