"""Petty cash report definitions (DEC-033): a fund statement with its running balance, and the expenses paid from
petty cash by category, machine and job. Rows reuse the petty cash ledger and the expense list query; a field user
(no oversight permission) only reaches the funds they hold."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.modules.expenses.models import Expense, ExpenseCategory, ExpensePaidFrom, ExpenseStatus
from asseta.modules.expenses.service import expense_list_query
from asseta.modules.finance.common import local_date, tenant_settings
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.principal import RequestContext
from asseta.modules.pettycash.models import PettyCashFund
from asseta.modules.pettycash.service import PettyCashService
from asseta.modules.reports.definitions import ReportColumn as C
from asseta.modules.reports.definitions import ReportDefinition
from asseta.modules.reports.sources_ops import job_numbers, machine_codes


class PettyCashStatementFilters(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    fund_id: uuid.UUID
    period_from: date | None = Field(default=None, alias="from", description="Tenant-local first day")
    period_to: date | None = Field(default=None, alias="to", description="Tenant-local last day (default: today)")


def _statement(session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int) -> list[dict[str, Any]]:
    assert isinstance(f, PettyCashStatementFilters) and ctx.tenant_id is not None
    svc = PettyCashService(session, ctx, now)
    fund = svc.fund(f.fund_id)
    last = f.period_to or local_date(tenant_settings(session, ctx.tenant_id).timezone, now)
    first = f.period_from or last.replace(day=1)
    st = svc.ledger.statement(fund, first, last)
    rows: list[dict[str, Any]] = [
        {
            "occurred_at": None,
            "figure": "opening",
            "reference": None,
            "note": f"Opening balance {first.isoformat()}",
            "money_in": None,
            "money_out": None,
            "running_balance": st.opening_balance,
            "currency": fund.currency,
        }
    ]
    rows += [
        {
            "occurred_at": line.occurred_at,
            "figure": line.figure.value,
            "reference": line.reference,
            "note": line.note,
            "money_in": line.money_in,
            "money_out": line.money_out,
            "running_balance": line.running_balance,
            "currency": fund.currency,
        }
        for line in st.lines
    ]
    return rows[: limit + 1]


PETTY_CASH_STATEMENT = ReportDefinition(
    code="petty_cash_statement",
    title="Petty cash fund statement",
    description="Every movement of one fund's balance with the running balance",
    scope=S.TENANT,
    permission="tenant.pettycash.read",
    columns=(
        C("occurred_at", "When", "instant", 1.2),
        C("figure", "Movement", width=1.2),
        C("reference", "Reference"),
        C("note", "Note", width=2.2),
        C("money_in", "In", "money"),
        C("money_out", "Out", "money"),
        C("running_balance", "Balance", "money"),
        C("currency", "Currency", width=0.6),
    ),
    source=_statement,
    filters=PettyCashStatementFilters,
    list_operation="getPettyCashFundStatement",
    notes=(
        "Balance = acknowledged fundings and top-ups - approved fund expenses - confirmed returns + adjustments "
        "- written-off differences - advances + change returned.",
    ),
)


class PettyCashExpensesFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    petty_cash_fund_id: uuid.UUID | None = None
    status: ExpenseStatus | None = None
    machine_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None


def _expenses(session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int) -> list[dict[str, Any]]:
    assert isinstance(f, PettyCashExpensesFilters)
    svc = PettyCashService(session, ctx, now)
    stmt = expense_list_query(
        f.status, f.machine_id, f.job_id, None, ExpensePaidFrom.PETTY_CASH, f.petty_cash_fund_id
    ).where(Expense.petty_cash_fund_id.in_(svc.visible_funds().with_only_columns(PettyCashFund.id)))
    expenses = list(session.execute(stmt.limit(limit + 1)).scalars())
    categories = dict(
        session.execute(
            select(ExpenseCategory.id, ExpenseCategory.name).where(
                ExpenseCategory.id.in_({e.category_id for e in expenses})
            )
        )
        .tuples()
        .all()
    )
    funds = dict(
        session.execute(
            select(PettyCashFund.id, PettyCashFund.name).where(
                PettyCashFund.id.in_({e.petty_cash_fund_id for e in expenses if e.petty_cash_fund_id})
            )
        )
        .tuples()
        .all()
    )
    machines = machine_codes(session, (e.machine_id for e in expenses))
    jobs = job_numbers(session, (e.job_id for e in expenses))
    return [
        {
            "incurred_at": e.incurred_at,
            "fund": funds.get(e.petty_cash_fund_id) if e.petty_cash_fund_id else None,
            "category": categories.get(e.category_id),
            "description": e.description,
            "supplier": e.supplier,
            "amount": e.amount,
            "currency": e.currency,
            "machine": machines.get(e.machine_id) if e.machine_id else None,
            "job": jobs.get(e.job_id) if e.job_id else None,
            "status": e.status,
            "flags": ", ".join(e.control_flags) or None,
            "decided_at": e.decided_at,
        }
        for e in expenses
    ]


PETTY_CASH_EXPENSES = ReportDefinition(
    code="petty_cash_expenses",
    title="Petty cash expenses",
    description="Expenses paid from petty cash funds by fund, category, machine and job, with approval status",
    scope=S.TENANT,
    permission="tenant.pettycash.read",
    columns=(
        C("incurred_at", "Incurred", "instant", 1.2),
        C("fund", "Fund", width=1.2),
        C("category", "Category"),
        C("description", "Description", width=2.0),
        C("supplier", "Supplier", width=1.1),
        C("amount", "Amount", "money"),
        C("currency", "Currency", width=0.6),
        C("machine", "Machine"),
        C("job", "Job"),
        C("status", "Status", width=1.2),
        C("flags", "Flags", width=1.2),
        C("decided_at", "Decided", "instant", 1.2),
    ),
    source=_expenses,
    filters=PettyCashExpensesFilters,
    list_operation="listExpenses",
)
