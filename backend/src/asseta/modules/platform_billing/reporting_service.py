"""Platform-owner dashboard: contracted MRR/ARR per currency (never summed across currencies), billable vs
enrolled asset counts, outstanding balances and churn events."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from asseta.modules.platform_billing.dto import Money
from asseta.modules.platform_billing.enums import BILLABLE_STATUSES, Cadence, InvoiceStatus, SubscriptionStatus
from asseta.modules.platform_billing.models_commercial import SubscriptionStatusEvent, TenantSubscription
from asseta.modules.platform_billing.models_ledger import PlatformInvoice
from asseta.modules.platform_billing.repository import BillingRepository
from asseta.modules.tenancy.models import Tenant

TWELVE = Decimal(12)


class CurrencyTotalsDto(BaseModel):
    currency: str
    contracted_mrr: Money
    contracted_arr: Money
    billable_assets: int
    enrolled_assets: int
    outstanding_balance: Money
    open_invoices: int


class PlatformDashboardDto(BaseModel):
    as_of: date
    tenants_by_status: dict[str, int]
    tenants_by_access: dict[str, int]
    subscriptions_by_status: dict[str, int]
    by_currency: list[CurrencyTotalsDto]
    churn_events_30d: int


class PlatformReportingService:
    def __init__(self, session: Session):
        self._s = session
        self._repo = BillingRepository(session)

    def _counts(self, column: InstrumentedAttribute[Any]) -> dict[str, int]:
        rows = self._s.execute(select(column, func.count()).group_by(column)).all()
        return {str(getattr(k, "value", k)): int(v) for k, v in rows}

    def dashboard(self, today: date) -> PlatformDashboardDto:
        mrr: dict[str, Decimal] = defaultdict(Decimal)
        billable: dict[str, int] = defaultdict(int)
        enrolled: dict[str, int] = defaultdict(int)
        subs = self._s.execute(select(TenantSubscription).where(TenantSubscription.status.in_(BILLABLE_STATUSES)))
        for sub in subs.scalars():
            rate = self._repo.rate_effective(sub.agreement_id, max(today, sub.billing_start_date))
            count = self._repo.count_active(sub.id, today)
            billed = max(count, rate.minimum_billable_assets)
            gross = rate.unit_price * billed * (1 - rate.discount_percent / 100)
            mrr[rate.currency] += gross if rate.cadence is Cadence.MONTHLY else gross / TWELVE
            billable[rate.currency] += billed
            enrolled[rate.currency] += count
        outstanding = self._s.execute(
            select(PlatformInvoice.currency, func.sum(PlatformInvoice.balance), func.count())
            .where(PlatformInvoice.status != InvoiceStatus.PAID)
            .group_by(PlatformInvoice.currency)
        ).all()
        open_by_currency = {c: (Decimal(b), int(n)) for c, b, n in outstanding}
        currencies = sorted(set(mrr) | set(open_by_currency))
        totals = [
            CurrencyTotalsDto(
                currency=c,
                contracted_mrr=mrr[c].quantize(Decimal("0.01")),
                contracted_arr=(mrr[c] * TWELVE).quantize(Decimal("0.01")),
                billable_assets=billable[c],
                enrolled_assets=enrolled[c],
                outstanding_balance=open_by_currency.get(c, (Decimal(0), 0))[0],
                open_invoices=open_by_currency.get(c, (Decimal(0), 0))[1],
            )
            for c in currencies
        ]
        churn = self._s.execute(
            select(func.count())
            .select_from(SubscriptionStatusEvent)
            .where(
                SubscriptionStatusEvent.to_status == SubscriptionStatus.CANCELLED.value,
                SubscriptionStatusEvent.effective_date >= today - timedelta(days=30),
            )
        ).scalar_one()
        return PlatformDashboardDto(
            as_of=today,
            tenants_by_status=self._counts(Tenant.status),
            tenants_by_access=self._counts(Tenant.access_state),
            subscriptions_by_status=self._counts(TenantSubscription.status),
            by_currency=totals,
            churn_events_30d=int(churn),
        )
