"""ADR-008 report definitions: what owners read once machine reports replace jobs. Customer hours (bought / used /
left), productive vs non-productive hours by machine and by reason (approved machine reports), sales and collections
by payment method, credit invoices and their payments. Cash per supervisor is the existing `cash` report. Row sources
reuse the list endpoints' queries and services with the same filters."""

import uuid
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.modules.customers.models import Customer
from asseta.modules.finance.common import local_bounds, local_date, tenant_settings
from asseta.modules.finance.models import CustomerPayment, SettlementStatus
from asseta.modules.fleet.models import Machine
from asseta.modules.hours.credit_invoices import invoice_dtos, invoice_query, local_today
from asseta.modules.hours.dto import CreditInvoiceStatus
from asseta.modules.hours.ledger import ZERO
from asseta.modules.hours.models import (
    CreditInvoice,
    CreditInvoicePayment,
    HoursPaymentAllocation,
    HoursPurchase,
)
from asseta.modules.hours.summary import customer_hours
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.principal import RequestContext
from asseta.modules.machine_reports.models import (
    MachineReport,
    MachineReportLine,
    MachineReportStatus,
    ReportLineKind,
)
from asseta.modules.machine_reports.service import report_scope
from asseta.modules.meter.engine_models import EngineHourReason
from asseta.modules.reports.definitions import ReportColumn as C
from asseta.modules.reports.definitions import ReportDefinition

HUNDRED = Decimal(100)


def _tid(ctx: RequestContext) -> uuid.UUID:
    assert ctx.tenant_id is not None
    return ctx.tenant_id


class _Period(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    period_from: date | None = Field(
        default=None, alias="from", description="Tenant-local first day (default: first day of this month)"
    )
    period_to: date | None = Field(default=None, alias="to", description="Tenant-local last day (default: today)")


def _bounds(session: Session, ctx: RequestContext, now: datetime, f: _Period) -> tuple[datetime, datetime]:
    tz = tenant_settings(session, _tid(ctx)).timezone
    today = local_date(tz, now)
    return local_bounds(tz, f.period_from or today.replace(day=1), f.period_to or today)


def _customers(session: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    return dict(session.execute(select(Customer.id, Customer.name).where(Customer.id.in_(ids))).tuples().all())


# --- customer hours: bought / used / left ------------------------------------------------------------------------
class CustomerHoursFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: uuid.UUID | None = None


def _customer_hours(
    session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int
) -> list[dict[str, Any]]:
    assert isinstance(f, CustomerHoursFilters)
    found = customer_hours(session, _tid(ctx), now, f.customer_id)
    names = _customers(session, {r.customer_id for r in found})
    rows = [{**r.model_dump(), "customer": names.get(r.customer_id)} for r in found]
    rows.sort(key=lambda r: str(r["customer"] or "").casefold())
    return rows[: limit + 1]


CUSTOMER_HOURS = ReportDefinition(
    code="customer_hours",
    title="Customer hours",
    description="Per customer: hours bought, activated, used, left and still awaiting payment or activation",
    scope=S.TENANT,
    permission="tenant.hours.read",
    columns=(
        C("customer", "Customer", width=2.0),
        C("bought", "Bought", "decimal"),
        C("activated", "Activated", "decimal"),
        C("used", "Used", "decimal"),
        C("left", "Left", "decimal"),
        C("awaiting_activation", "Awaiting activation", "decimal", 1.2),
        C("credit_owed", "Credit owed", "money"),
    ),
    source=_customer_hours,
    filters=CustomerHoursFilters,
    list_operation="listCustomerHours",
    landscape=False,
    notes=("Left = activated - used - expired - cancelled - refunded (+/- transfers and corrections).",),
)


# --- productive vs non-productive hours ---------------------------------------------------------------------------
class MachineHoursFilters(_Period):
    machine_id: uuid.UUID | None = None


def _machine_hours(
    session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int
) -> list[dict[str, Any]]:
    assert isinstance(f, MachineHoursFilters)
    start, end = _bounds(session, ctx, now, f)
    stmt = (
        select(
            MachineReport.machine_id,
            MachineReportLine.kind,
            MachineReportLine.reason_id,
            func.sum(MachineReportLine.hours),
        )
        .join(MachineReportLine, MachineReportLine.report_id == MachineReport.id)
        .where(
            MachineReport.status == MachineReportStatus.APPROVED,
            MachineReport.end_at >= start,
            MachineReport.end_at < end,
        )
        .group_by(MachineReport.machine_id, MachineReportLine.kind, MachineReportLine.reason_id)
    )
    if (scope := report_scope(session, ctx)) is not None:
        stmt = stmt.where(scope)
    if f.machine_id is not None:
        stmt = stmt.where(MachineReport.machine_id == f.machine_id)
    found = list(session.execute(stmt).tuples())
    totals: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for machine_id, _, _, hours in found:
        totals[machine_id] += Decimal(hours)
    machines = (
        {m.id: m for m in session.execute(select(Machine).where(Machine.id.in_(set(totals)))).scalars()}
        if totals
        else {}
    )
    reasons = dict(
        session.execute(
            select(EngineHourReason.id, EngineHourReason.name).where(
                EngineHourReason.id.in_({r for _, _, r, _ in found if r is not None})
            )
        )
        .tuples()
        .all()
    )
    rows = []
    for machine_id, kind, reason_id, hours in found:
        m = machines.get(machine_id)
        productive = kind is ReportLineKind.CUSTOMER
        rows.append(
            {
                "machine": m.asset_code if m else None,
                "machine_name": m.name if m else None,
                "kind": "PRODUCTIVE" if productive else "NON_PRODUCTIVE",
                "reason": "Customer work" if productive or reason_id is None else reasons.get(reason_id),
                "hours": Decimal(hours),
                "share_percent": (Decimal(hours) * HUNDRED / totals[machine_id]).quantize(Decimal("0.1")),
                "machine_total": totals[machine_id],
            }
        )
    rows.sort(key=lambda r: (str(r["machine"] or ""), r["kind"] != "PRODUCTIVE", str(r["reason"] or "")))
    return rows[: limit + 1]


MACHINE_HOURS = ReportDefinition(
    code="machine_hours",
    title="Productive and non-productive hours",
    description="Approved machine report hours per machine: customer work and each non-productive reason",
    scope=S.TENANT,
    permission="tenant.machine_report.read",
    columns=(
        C("machine", "Machine"),
        C("machine_name", "Name", width=1.4),
        C("kind", "Kind", width=1.1),
        C("reason", "Reason", width=1.6),
        C("hours", "Hours", "decimal"),
        C("share_percent", "Share %", "decimal", 0.7),
        C("machine_total", "Machine total", "decimal"),
    ),
    source=_machine_hours,
    filters=MachineHoursFilters,
    list_operation="listMachineReports",
    notes=("Only approved machine reports count, by the day of their new reading (tenant-local).",),
)


# --- sales and collections by method ------------------------------------------------------------------------------
METHODS = ("CASH", "BANK", "MOBILE_MONEY", "CREDIT", "UNPAID")


def _sales(session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int) -> list[dict[str, Any]]:
    assert isinstance(f, _Period)
    start, end = _bounds(session, ctx, now, f)
    sold: dict[tuple[str, str], Decimal] = defaultdict(lambda: ZERO)
    purchases = list(
        session.execute(
            select(HoursPurchase).where(
                HoursPurchase.cancelled_at.is_(None),
                HoursPurchase.created_at >= start,
                HoursPurchase.created_at < end,
            )
        ).scalars()
    )
    ids = [p.id for p in purchases]
    covered: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    if ids:
        for pid, currency, method, amount in session.execute(
            select(HoursPurchase.id, HoursPurchase.currency, CustomerPayment.method, HoursPaymentAllocation.amount)
            .join(HoursPaymentAllocation, HoursPaymentAllocation.purchase_id == HoursPurchase.id)
            .join(CustomerPayment, CustomerPayment.id == HoursPaymentAllocation.payment_id)
            .where(
                HoursPurchase.id.in_(ids),
                HoursPaymentAllocation.released_at.is_(None),
                CustomerPayment.status != SettlementStatus.REJECTED,
                # money taken with the sale (credit-invoice payments count as collections, not as the sale's method)
                CustomerPayment.id.not_in(select(CreditInvoicePayment.payment_id)),
            )
        ).tuples():
            sold[(method.value, currency)] += amount
            covered[pid] += amount
        for pid, currency, amount in session.execute(
            select(CreditInvoice.purchase_id, CreditInvoice.currency, CreditInvoice.amount).where(
                CreditInvoice.purchase_id.in_(ids)
            )
        ).tuples():
            sold[("CREDIT", currency)] += amount
            covered[pid] += amount
    for p in purchases:
        if (gap := p.amount - covered[p.id]) > 0:
            sold[("UNPAID", p.currency)] += gap
    collected: dict[tuple[str, str], list[Decimal]] = defaultdict(lambda: [ZERO, ZERO])
    for method, currency, status, amount in session.execute(
        select(CustomerPayment.method, CustomerPayment.currency, CustomerPayment.status, CustomerPayment.amount).where(
            CustomerPayment.received_at >= start,
            CustomerPayment.received_at < end,
            CustomerPayment.status != SettlementStatus.REJECTED,
            CustomerPayment.reversed_at.is_(None),
        )
    ).tuples():
        figures = collected[(method.value, currency)]
        figures[0] += amount
        if status is SettlementStatus.VERIFIED:
            figures[1] += amount
    keys = sorted({*sold, *collected}, key=lambda k: (k[1], METHODS.index(k[0]) if k[0] in METHODS else 99))
    return [
        {
            "method": method,
            "currency": currency,
            "sold": sold.get((method, currency), ZERO),
            "collected": collected[(method, currency)][0] if (method, currency) in collected else ZERO,
            "verified": collected[(method, currency)][1] if (method, currency) in collected else ZERO,
        }
        for method, currency in keys
    ][: limit + 1]


SALES_COLLECTIONS = ReportDefinition(
    code="sales_collections",
    title="Sales and collections by method",
    description="Hours sold in the period by payment line (cash, bank, mobile money, credit, unpaid) and money "
    "received in the period by method",
    scope=S.TENANT,
    permission="tenant.finance.read",
    columns=(
        C("method", "Method"),
        C("currency", "Currency", width=0.6),
        C("sold", "Sold", "money"),
        C("collected", "Collected", "money"),
        C("verified", "Of which verified", "money"),
    ),
    source=_sales,
    filters=_Period,
    list_operation="listHoursPurchases",
    landscape=False,
    notes=(
        "Sold: orders recorded in the period (not cancelled) by their payment lines; CREDIT is the credit invoices; "
        "UNPAID is what no line covers. Collected: customer payments received in the period (not rejected or "
        "reversed), credit-invoice payments included.",
    ),
)


# --- credit invoices and their payments --------------------------------------------------------------------------
class CreditInvoiceFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: uuid.UUID | None = None
    status: CreditInvoiceStatus | None = None
    overdue: bool | None = None


def _invoices(session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int) -> list[dict[str, Any]]:
    assert isinstance(f, CreditInvoiceFilters)
    stmt = invoice_query(local_today(session, _tid(ctx), now), None, f.customer_id, f.status, f.overdue)
    invoices = list(session.execute(stmt.limit(limit + 1)).scalars())
    dtos = invoice_dtos(session, _tid(ctx), now, invoices, with_payments=False)
    names = _customers(session, {d.customer_id for d in dtos})
    return [
        {
            "invoice_number": d.invoice_number,
            "customer": names.get(d.customer_id),
            "order": d.purchase_number,
            "issued_at": d.issued_at,
            "due_date": d.due_date,
            "currency": d.currency,
            "amount": d.amount,
            "paid": d.paid,
            "balance": d.balance,
            "status": d.status,
            "days_overdue": d.days_overdue,
        }
        for d in dtos
    ]


CREDIT_INVOICES = ReportDefinition(
    code="credit_invoices",
    title="Credit invoices",
    description="Credit invoices of orders: amount, paid, balance, status and days overdue",
    scope=S.TENANT,
    permission="tenant.hours.read",
    columns=(
        C("invoice_number", "Invoice", width=1.1),
        C("customer", "Customer", width=1.6),
        C("order", "Order", width=1.1),
        C("issued_at", "Issued", "instant", 1.1),
        C("due_date", "Due", "date", 0.9),
        C("currency", "Currency", width=0.6),
        C("amount", "Amount", "money"),
        C("paid", "Paid", "money"),
        C("balance", "Balance", "money"),
        C("status", "Status", width=0.9),
        C("days_overdue", "Days overdue", "int", 0.8),
    ),
    source=_invoices,
    filters=CreditInvoiceFilters,
    list_operation="listCreditInvoices",
    notes=("Paid counts every recorded payment that is not rejected or reversed (claimed or verified).",),
)


class InvoicePaymentFilters(_Period):
    customer_id: uuid.UUID | None = None


def _invoice_payments(
    session: Session, ctx: RequestContext, now: datetime, f: BaseModel, limit: int
) -> list[dict[str, Any]]:
    assert isinstance(f, InvoicePaymentFilters)
    start, end = _bounds(session, ctx, now, f)
    stmt = (
        select(CreditInvoice, CreditInvoicePayment, CustomerPayment)
        .join(CreditInvoicePayment, CreditInvoicePayment.invoice_id == CreditInvoice.id)
        .join(CustomerPayment, CustomerPayment.id == CreditInvoicePayment.payment_id)
        .where(CustomerPayment.received_at >= start, CustomerPayment.received_at < end)
        .order_by(CustomerPayment.received_at, CreditInvoice.invoice_number)
    )
    if f.customer_id is not None:
        stmt = stmt.where(CreditInvoice.customer_id == f.customer_id)
    found = list(session.execute(stmt.limit(limit + 1)).tuples())
    names = _customers(session, {inv.customer_id for inv, _, _ in found})
    return [
        {
            "received_at": pay.received_at,
            "invoice_number": inv.invoice_number,
            "customer": names.get(inv.customer_id),
            "method": pay.method,
            "reference": pay.reference or pay.collection_number,
            "currency": inv.currency,
            "amount": link.amount,
            "status": "REVERSED" if pay.reversed_at is not None else pay.status,
        }
        for inv, link, pay in found
    ]


CREDIT_INVOICE_PAYMENTS = ReportDefinition(
    code="credit_invoice_payments",
    title="Credit invoice payments",
    description="Payments of credit invoices received in the period, by method",
    scope=S.TENANT,
    permission="tenant.hours.read",
    columns=(
        C("received_at", "Received", "instant", 1.1),
        C("invoice_number", "Invoice", width=1.1),
        C("customer", "Customer", width=1.6),
        C("method", "Method"),
        C("reference", "Reference", width=1.2),
        C("currency", "Currency", width=0.6),
        C("amount", "Amount", "money"),
        C("status", "Status", width=0.9),
    ),
    source=_invoice_payments,
    filters=InvoicePaymentFilters,
    list_operation="listCreditInvoices",
)
