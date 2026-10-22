"""Money report definitions: supervisor cash, expenses and subscription (tenant + platform). Row sources reuse the
list endpoints' query builders/services with identical filters and sort."""

import uuid
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.modules.expenses.models import ExpenseCategory, ExpenseStatus
from asseta.modules.expenses.service import expense_list_query
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.common import tenant_settings
from asseta.modules.fleet.models import StaffMember
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.principal import RequestContext
from asseta.modules.platform_billing.enums import InvoiceKind, InvoiceStatus
from asseta.modules.platform_billing.models_ledger import SubscriptionAssetEnrollment
from asseta.modules.platform_billing.repository import (
    BillingRepository,
    platform_invoice_query,
    tenant_invoice_query,
)
from asseta.modules.reports.definitions import ReportColumn as C
from asseta.modules.reports.definitions import ReportDefinition
from asseta.modules.reports.sources_ops import job_numbers, machine_codes
from asseta.modules.tenancy.models import Tenant


class _Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _tid(ctx: RequestContext) -> uuid.UUID:
    assert ctx.tenant_id is not None
    return ctx.tenant_id


# --- supervisor cash --------------------------------------------------------------------------------------------
class CashReportFilters(_Filters):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    period_from: date | None = Field(
        default=None, alias="from", description="Tenant-local first day (default: first day of this month)"
    )
    period_to: date | None = Field(default=None, alias="to", description="Tenant-local last day (default: today)")
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    staff_member_id: uuid.UUID | None = None


def _cash(session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int) -> list[dict[str, Any]]:
    assert isinstance(f, CashReportFilters)
    today = now.astimezone(ZoneInfo(tenant_settings(session, _tid(ctx)).timezone)).date()
    first, last = f.period_from or today.replace(day=1), f.period_to or today
    rows = CashCustodyService(session, ctx, now).supervisor_summaries(first, last, f.currency, f.staff_member_id)
    return [r.model_dump() for r in rows[: limit + 1]]


CASH = ReportDefinition(
    code="cash",
    title="Supervisor cash reconciliation",
    description="Per supervisor and currency: floats, collections, approved spending, verified handovers, outstanding",
    scope=S.TENANT,
    permission="tenant.finance.read",
    columns=(
        C("staff_name", "Supervisor", width=1.6),
        C("currency", "Currency", width=0.6),
        C("period_from", "From", "date", 0.9),
        C("period_to", "To", "date", 0.9),
        C("opening", "Opening", "money"),
        C("floats_issued", "Floats issued", "money"),
        C("collections", "Collections", "money"),
        C("approved_spending", "Approved spending", "money"),
        C("verified_handovers", "Verified handovers", "money"),
        C("closing_outstanding", "Outstanding", "money"),
        C("claimed_unverified_handovers", "Claimed handovers (unverified)", "money", 1.2),
        C("pending_spending", "Pending spending", "money"),
        C("unverified_collections", "Unverified collections", "money"),
    ),
    source=_cash,
    filters=CashReportFilters,
    list_operation="listCashSupervisorSummaries",
    notes=("Outstanding = opening + floats + collections - approved spending - verified handovers.",),
)


# --- expenses ---------------------------------------------------------------------------------------------------
class ExpensesReportFilters(_Filters):
    status: ExpenseStatus | None = None
    machine_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    custodian_staff_id: uuid.UUID | None = None


def _expenses(session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int) -> list[dict[str, Any]]:
    assert isinstance(f, ExpensesReportFilters)
    stmt = expense_list_query(f.status, f.machine_id, f.job_id, f.custodian_staff_id)
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
    staff = dict(
        session.execute(
            select(StaffMember.id, StaffMember.full_name).where(
                StaffMember.id.in_({e.custodian_staff_id for e in expenses if e.custodian_staff_id})
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
            "category": categories.get(e.category_id),
            "description": e.description,
            "supplier": e.supplier,
            "amount": e.amount,
            "currency": e.currency,
            "paid_from": e.paid_from,
            "custodian": staff.get(e.custodian_staff_id) if e.custodian_staff_id else None,
            "machine": machines.get(e.machine_id) if e.machine_id else None,
            "job": jobs.get(e.job_id) if e.job_id else None,
            "status": e.status,
            "decided_at": e.decided_at,
        }
        for e in expenses
    ]


EXPENSES = ReportDefinition(
    code="expenses",
    title="Expenses",
    description="Expenses with category, amount, how paid, custodian, machine/job and approval status",
    scope=S.TENANT,
    permission="tenant.expense.read",
    columns=(
        C("incurred_at", "Incurred", "instant", 1.2),
        C("category", "Category"),
        C("description", "Description", width=2.2),
        C("supplier", "Supplier", width=1.2),
        C("amount", "Amount", "money"),
        C("currency", "Currency", width=0.6),
        C("paid_from", "Paid from", width=1.1),
        C("custodian", "Custodian", width=1.2),
        C("machine", "Machine"),
        C("job", "Job"),
        C("status", "Status", width=1.2),
        C("decided_at", "Decided", "instant", 1.2),
    ),
    source=_expenses,
    filters=ExpensesReportFilters,
    list_operation="listExpenses",
)


# --- subscription (tenant) --------------------------------------------------------------------------------------
class SubscriptionReportFilters(_Filters):
    pass


def _subscription(
    session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for inv in session.execute(tenant_invoice_query().limit(limit + 1)).scalars():
        rows.append(
            {
                "record": f"INVOICE ({inv.kind.value})",
                "reference": inv.invoice_number,
                "start": inv.period_start,
                "end": inv.period_end,
                "status": inv.status,
                "due_date": inv.due_date,
                "currency": inv.currency,
                "total": inv.total,
                "paid": inv.amount_paid,
                "balance": inv.balance,
            }
        )
    sub = BillingRepository(session).current_subscription_for_tenant(_tid(ctx))
    if sub is not None and len(rows) <= limit:
        e = SubscriptionAssetEnrollment
        stmt = select(e).where(e.subscription_id == sub.id).order_by(e.asset_label).limit(limit + 1 - len(rows))
        for en in session.execute(stmt).scalars():
            rows.append(
                {
                    "record": "ENROLLMENT",
                    "reference": en.asset_label,
                    "start": en.effective_from,
                    "end": en.effective_to,
                    "status": "ENDED" if en.effective_to and en.effective_to <= now.date() else "ACTIVE",
                }
            )
    return rows


_SUBSCRIPTION_COLUMNS = (
    C("record", "Record", width=1.3),
    C("reference", "Invoice / asset", width=1.4),
    C("start", "From", "date"),
    C("end", "To", "date"),
    C("status", "Status"),
    C("due_date", "Due", "date"),
    C("currency", "Currency", width=0.6),
    C("total", "Total", "money"),
    C("paid", "Paid", "money"),
    C("balance", "Balance", "money"),
)

SUBSCRIPTION = ReportDefinition(
    code="subscription",
    title="Asseta subscription",
    description="Your Asseta invoices (latest period first) and billable machine enrollments",
    scope=S.TENANT,
    permission="tenant.billing.read",
    columns=_SUBSCRIPTION_COLUMNS,
    source=_subscription,
    filters=SubscriptionReportFilters,
    list_operation="listMyPlatformInvoices",
)


# --- subscription (platform) ------------------------------------------------------------------------------------
class PlatformSubscriptionReportFilters(_Filters):
    tenant_id: uuid.UUID | None = None
    status: InvoiceStatus | None = None
    kind: InvoiceKind | None = None


def _platform_subscription(
    session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int
) -> list[dict[str, Any]]:
    assert isinstance(f, PlatformSubscriptionReportFilters)
    invoices = list(session.execute(platform_invoice_query(f.tenant_id, f.status, f.kind).limit(limit + 1)).scalars())
    tenants = dict(
        session.execute(select(Tenant.id, Tenant.display_name).where(Tenant.id.in_({i.tenant_id for i in invoices})))
        .tuples()
        .all()
    )
    return [
        {
            "tenant": tenants.get(i.tenant_id),
            "invoice_number": i.invoice_number,
            "kind": i.kind,
            "period_start": i.period_start,
            "period_end": i.period_end,
            "status": i.status,
            "issued_at": i.issued_at,
            "due_date": i.due_date,
            "billable_assets": i.billable_assets,
            "currency": i.currency,
            "total": i.total,
            "paid": i.amount_paid,
            "balance": i.balance,
        }
        for i in invoices
    ]


PLATFORM_SUBSCRIPTION = ReportDefinition(
    code="subscription",
    title="Tenant subscription invoices",
    description="Platform invoices per tenant (latest issued first) with payment status",
    scope=S.PLATFORM,
    permission="platform.invoice.read",
    columns=(
        C("tenant", "Tenant", width=1.6),
        C("invoice_number", "Invoice", width=1.3),
        C("kind", "Kind"),
        C("period_start", "Period start", "date"),
        C("period_end", "Period end", "date"),
        C("status", "Status"),
        C("issued_at", "Issued", "instant", 1.2),
        C("due_date", "Due", "date"),
        C("billable_assets", "Billable assets", "int", 0.8),
        C("currency", "Currency", width=0.6),
        C("total", "Total", "money"),
        C("paid", "Paid", "money"),
        C("balance", "Balance", "money"),
    ),
    source=_platform_subscription,
    filters=PlatformSubscriptionReportFilters,
    list_operation="listPlatformInvoices",
)
