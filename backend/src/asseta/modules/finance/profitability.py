"""Basic profitability by machine / customer for a tenant-local period, per currency (never mixed) (ADR-008).

Recognized revenue = customer hours used in approved machine reports, valued at the effective hourly price of the
order each hour came from, dated when the report was approved and attributed to the machine that did the work and to
the customer. Direct costs = APPROVED expenses (by category, dated `incurred_at`) + attributed fuel cost (ISSUE events,
and PURCHASE events straight into a machine), attributed to their machine; grouped by customer they are not
attributable and show as one "Unattributed" row. To avoid double counting, an expense that paid for a fuel PURCHASE is
costed through the fuel event, and such a purchase counts only while its expense is APPROVED. Rejected and pending
expenses never count."""

import uuid
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, aliased

from asseta.core.db import utcnow
from asseta.core.money import quantize
from asseta.modules.customers.models import Customer
from asseta.modules.expenses.models import Expense, ExpenseCategory, ExpenseStatus, FuelEvent, FuelEventType
from asseta.modules.finance.common import ZERO, local_bounds, tenant_settings
from asseta.modules.finance.dto import ProfitabilityDto, ProfitabilityRowDto
from asseta.modules.fleet.models import Machine
from asseta.modules.hours.models import HoursLedgerEntry, HoursPurchase, LedgerEntryType
from asseta.modules.machine_reports.models import MachineReport
from asseta.modules.platform_billing.models_commercial import Currency
from asseta.modules.policy.capabilities import FUEL, capability_on

GroupBy = Literal["MACHINE", "CUSTOMER"]
Key = tuple[uuid.UUID | None, str]  # (group key, currency)


class ProfitabilityService:
    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self._s, self._tid = session, tenant_id

    def _revenue(self, group_by: GroupBy, start: datetime, end: datetime) -> dict[Key, Decimal]:
        key = MachineReport.machine_id if group_by == "MACHINE" else HoursLedgerEntry.customer_id
        units = dict(self._s.execute(select(Currency.code, Currency.minor_units)).tuples().all())
        out: dict[Key, Decimal] = defaultdict(lambda: ZERO)
        rows = self._s.execute(
            select(key, HoursPurchase.currency, HoursLedgerEntry.hours, HoursPurchase.effective_rate)
            .join(MachineReport, MachineReport.id == HoursLedgerEntry.machine_report_id)
            .join(HoursPurchase, HoursPurchase.id == HoursLedgerEntry.purchase_id)
            .where(
                HoursLedgerEntry.entry_type == LedgerEntryType.CONSUMED,
                HoursLedgerEntry.occurred_at >= start,
                HoursLedgerEntry.occurred_at < end,
            )
        ).tuples()
        for k, currency, hours, rate in rows:
            out[(k, currency)] += quantize(hours * rate, int(units.get(currency, 2)))
        return out

    def _costs(self, group_by: GroupBy, start: datetime, end: datetime) -> dict[Key, dict[str, Decimal]]:
        out: dict[Key, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        by_machine = group_by == "MACHINE"

        def key(machine_col: Any) -> Any:
            return machine_col if by_machine else None

        fuel_paid = select(FuelEvent.expense_id).where(FuelEvent.expense_id.is_not(None))
        expenses = self._s.execute(
            select(Expense.machine_id, Expense.currency, ExpenseCategory.code, Expense.amount)
            .join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
            .where(
                Expense.status == ExpenseStatus.APPROVED,
                Expense.incurred_at >= start,
                Expense.incurred_at < end,
                Expense.id.not_in(fuel_paid),
            )
        ).tuples()
        for machine_id, currency, code, amount in expenses:
            out[(key(machine_id), currency)][code] += amount
        if not capability_on(self._s, self._tid, FUEL, utcnow()):
            return out  # ADR-008 §3: no fuel line while the company has fuel switched off
        paying = aliased(Expense)
        fuel = self._s.execute(
            select(FuelEvent.machine_id, FuelEvent.currency, FuelEvent.attributed_cost)
            .outerjoin(paying, paying.id == FuelEvent.expense_id)
            .where(
                FuelEvent.occurred_at >= start,
                FuelEvent.occurred_at < end,
                or_(
                    FuelEvent.event_type == FuelEventType.ISSUE,
                    and_(
                        FuelEvent.event_type == FuelEventType.PURCHASE,
                        FuelEvent.machine_id.is_not(None),
                        or_(FuelEvent.expense_id.is_(None), paying.status == ExpenseStatus.APPROVED),
                    ),
                ),
            )
        ).tuples()
        for machine_id, currency, cost in fuel:
            out[(key(machine_id), currency)]["FUEL"] += cost
        return out

    def _labels(self, group_by: GroupBy, keys: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not keys:
            return {}
        if group_by == "MACHINE":
            rows = self._s.execute(select(Machine.id, Machine.asset_code, Machine.name).where(Machine.id.in_(keys)))
            return {i: f"{code} {name}" for i, code, name in rows.tuples()}
        return dict(self._s.execute(select(Customer.id, Customer.name).where(Customer.id.in_(keys))).tuples().all())

    def report(self, group_by: GroupBy, first: date, last: date) -> ProfitabilityDto:
        tz = tenant_settings(self._s, self._tid).timezone
        start, end = local_bounds(tz, first, last)
        revenue, costs = self._revenue(group_by, start, end), self._costs(group_by, start, end)
        labels = self._labels(group_by, {k for k, _ in (*revenue, *costs) if k is not None})
        rows = []
        for key in sorted({*revenue, *costs}, key=lambda k: (k[1], k[0] is None, labels.get(k[0], "") if k[0] else "")):
            earned = revenue.get(key, ZERO)
            cats = dict(costs.get(key, {}))
            fuel = cats.get("FUEL", ZERO)
            expense = sum((v for c, v in cats.items() if c != "FUEL"), ZERO)
            rows.append(
                ProfitabilityRowDto(
                    group_key=key[0],
                    label=labels.get(key[0], "") if key[0] else "Unattributed",
                    currency=key[1],
                    revenue=earned,
                    net_revenue=earned,
                    expense_cost=expense,
                    fuel_cost=fuel,
                    direct_cost=expense + fuel,
                    margin=earned - expense - fuel,
                    cost_by_category=dict(sorted(cats.items())),
                )
            )
        return ProfitabilityDto(group_by=group_by, period_from=first, period_to=last, timezone=tz, rows=rows)
