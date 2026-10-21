"""Basic profitability by machine / job / customer for a tenant-local period, per currency (never mixed).

Recognized revenue = issued hire-invoice lines excluding tax (discounts included as negative lines), dated at
issue; a voided invoice reverses its lines at the void date. Direct costs = APPROVED expenses (by category, dated
`incurred_at`) + attributed fuel cost (ISSUE events, and PURCHASE events straight into a machine). To avoid double
counting, an expense that paid for a fuel PURCHASE is costed through the fuel event, and such a purchase counts
only while its expense is APPROVED. Rejected and pending expenses never count."""

import uuid
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, aliased

from asseta.modules.expenses.models import Expense, ExpenseCategory, ExpenseStatus, FuelEvent, FuelEventType
from asseta.modules.finance.common import ZERO, local_bounds, tenant_settings
from asseta.modules.finance.dto import ProfitabilityDto, ProfitabilityRowDto
from asseta.modules.finance.models import HireInvoiceLine, TenantHireInvoice
from asseta.modules.fleet.models import Machine
from asseta.modules.jobs.charges import ChargeKind
from asseta.modules.jobs.models import Customer, Job, RentalContract

GroupBy = Literal["MACHINE", "JOB", "CUSTOMER"]
Key = tuple[uuid.UUID | None, str]  # (group key, currency)


class ProfitabilityService:
    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self._s, self._tid = session, tenant_id

    def _revenue(self, group_by: GroupBy, start: datetime, end: datetime) -> dict[Key, list[Decimal]]:
        key = {
            "MACHINE": HireInvoiceLine.machine_id,
            "JOB": HireInvoiceLine.job_id,
            "CUSTOMER": TenantHireInvoice.customer_id,
        }[group_by]
        out: dict[Key, list[Decimal]] = defaultdict(lambda: [ZERO, ZERO])
        rows = self._s.execute(
            select(
                key,
                TenantHireInvoice.currency,
                HireInvoiceLine.amount,
                TenantHireInvoice.issued_at,
                TenantHireInvoice.voided_at,
            )
            .join(TenantHireInvoice, TenantHireInvoice.id == HireInvoiceLine.invoice_id)
            .where(
                HireInvoiceLine.kind != ChargeKind.TAX,
                TenantHireInvoice.issued_at.is_not(None),
                or_(
                    and_(TenantHireInvoice.issued_at >= start, TenantHireInvoice.issued_at < end),
                    and_(TenantHireInvoice.voided_at >= start, TenantHireInvoice.voided_at < end),
                ),
            )
        ).tuples()
        for k, currency, amount, issued_at, voided_at in rows:
            if issued_at is not None and start <= issued_at < end:
                out[(k, currency)][0] += amount
            if voided_at is not None and start <= voided_at < end:
                out[(k, currency)][1] += amount
        return out

    def _cost_key(self, group_by: GroupBy, machine_col: Any, job_col: Any, customer_col: Any) -> Any:
        return {"MACHINE": machine_col, "JOB": job_col, "CUSTOMER": customer_col}[group_by]

    def _costs(self, group_by: GroupBy, start: datetime, end: datetime) -> dict[Key, dict[str, Decimal]]:
        out: dict[Key, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        job, contract = aliased(Job), aliased(RentalContract)
        fuel_paid = select(FuelEvent.expense_id).where(FuelEvent.expense_id.is_not(None))
        expenses = self._s.execute(
            select(
                self._cost_key(group_by, Expense.machine_id, Expense.job_id, contract.customer_id),
                Expense.currency,
                ExpenseCategory.code,
                Expense.amount,
            )
            .join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
            .outerjoin(job, job.id == Expense.job_id)
            .outerjoin(contract, contract.id == job.contract_id)
            .where(
                Expense.status == ExpenseStatus.APPROVED,
                Expense.incurred_at >= start,
                Expense.incurred_at < end,
                Expense.id.not_in(fuel_paid),
            )
        ).tuples()
        for k, currency, code, amount in expenses:
            out[(k, currency)][code] += amount
        paying = aliased(Expense)
        fuel = self._s.execute(
            select(
                self._cost_key(group_by, FuelEvent.machine_id, FuelEvent.job_id, contract.customer_id),
                FuelEvent.currency,
                FuelEvent.attributed_cost,
            )
            .outerjoin(job, job.id == FuelEvent.job_id)
            .outerjoin(contract, contract.id == job.contract_id)
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
        for k, currency, cost in fuel:
            out[(k, currency)]["FUEL"] += cost
        return out

    def _labels(self, group_by: GroupBy, keys: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not keys:
            return {}
        if group_by == "MACHINE":
            rows = self._s.execute(select(Machine.id, Machine.asset_code, Machine.name).where(Machine.id.in_(keys)))
            return {i: f"{code} {name}" for i, code, name in rows.tuples()}
        if group_by == "JOB":
            return dict(self._s.execute(select(Job.id, Job.job_number).where(Job.id.in_(keys))).tuples().all())
        return dict(self._s.execute(select(Customer.id, Customer.name).where(Customer.id.in_(keys))).tuples().all())

    def report(self, group_by: GroupBy, first: date, last: date) -> ProfitabilityDto:
        tz = tenant_settings(self._s, self._tid).timezone
        start, end = local_bounds(tz, first, last)
        revenue, costs = self._revenue(group_by, start, end), self._costs(group_by, start, end)
        labels = self._labels(group_by, {k for k, _ in (*revenue, *costs) if k is not None})
        rows = []
        for key in sorted({*revenue, *costs}, key=lambda k: (k[1], k[0] is None, labels.get(k[0], "") if k[0] else "")):
            gross, reversed_ = revenue.get(key, [ZERO, ZERO])
            cats = dict(costs.get(key, {}))
            fuel = cats.get("FUEL", ZERO)
            expense = sum((v for c, v in cats.items() if c != "FUEL"), ZERO)
            net = gross - reversed_
            rows.append(
                ProfitabilityRowDto(
                    group_key=key[0],
                    label=labels.get(key[0], "") if key[0] else "Unattributed",
                    currency=key[1],
                    revenue=gross,
                    reversed_revenue=reversed_,
                    net_revenue=net,
                    expense_cost=expense,
                    fuel_cost=fuel,
                    direct_cost=expense + fuel,
                    margin=net - expense - fuel,
                    cost_by_category=dict(sorted(cats.items())),
                )
            )
        return ProfitabilityDto(group_by=group_by, period_from=first, period_to=last, timezone=tz, rows=rows)
