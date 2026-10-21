"""ORM -> DTO mapping and domain-term construction for platform billing."""

from datetime import date

from asseta.modules.platform_billing.calendar import Period, period_containing
from asseta.modules.platform_billing.dto import InvoiceDto, InvoiceLineDto, RateVersionDto
from asseta.modules.platform_billing.models_commercial import Currency, SubscriptionRateVersion, TenantSubscription
from asseta.modules.platform_billing.models_ledger import PlatformInvoice, PlatformInvoiceLine
from asseta.modules.platform_billing.pricing import RateTerms


def rate_terms(rate: SubscriptionRateVersion, currency: Currency) -> RateTerms:
    return RateTerms(
        unit_price=rate.unit_price,
        minimum_billable_assets=rate.minimum_billable_assets,
        discount_percent=rate.discount_percent,
        tax_name=rate.tax_name,
        tax_rate_percent=rate.tax_rate_percent,
        minor_units=currency.minor_units,
        rounding=rate.rounding_mode,
        mid_cycle_add=rate.mid_cycle_add,
        mid_cycle_remove=rate.mid_cycle_remove,
    )


def rate_dto(rate: SubscriptionRateVersion) -> RateVersionDto:
    return RateVersionDto.model_validate(rate)


def period_for(sub: TenantSubscription, rate: SubscriptionRateVersion, on: date) -> Period:
    return period_containing(sub.billing_start_date, sub.billing_anchor_day, rate.cadence, on)


def invoice_dto(inv: PlatformInvoice, lines: list[PlatformInvoiceLine]) -> InvoiceDto:
    return InvoiceDto(
        id=inv.id,
        tenant_id=inv.tenant_id,
        invoice_number=inv.invoice_number,
        period_start=inv.period_start,
        period_end=inv.period_end,
        currency=inv.currency,
        enrolled_assets=inv.enrolled_assets,
        billable_assets=inv.billable_assets,
        subtotal=inv.subtotal,
        discount_total=inv.discount_total,
        tax_total=inv.tax_total,
        total=inv.total,
        amount_paid=inv.amount_paid,
        credits_applied=inv.credits_applied,
        balance=inv.balance,
        status=inv.status,
        due_date=inv.due_date,
        issued_at=inv.issued_at,
        lines=[InvoiceLineDto.model_validate(line) for line in lines],
    )
