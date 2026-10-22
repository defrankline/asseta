"""Customer balances and statements, per currency (never mixed). Only issued invoices, reversal adjustments and
VERIFIED payments move the balance; claimed-but-unverified payments are reported separately."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import ColumnElement, ScalarSelect, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Executable

from asseta.core.errors import NotFound
from asseta.modules.finance.common import ZERO, local_bounds, tenant_settings
from asseta.modules.finance.dto import CustomerBalanceDto, CustomerStatementDto, StatementLineDto
from asseta.modules.finance.invoice_service import verified_paid
from asseta.modules.finance.models import (
    CustomerPayment,
    FinancialAdjustment,
    HireInvoiceStatus,
    HirePaymentAllocation,
    SettlementStatus,
    TenantHireInvoice,
)
from asseta.modules.finance.payment_service import payment_dto
from asseta.modules.jobs.models import Customer

Kind = Literal["INVOICE", "REVERSAL", "PAYMENT"]


@dataclass(frozen=True)
class ReceivableTotals:
    """Open customer receivables in one currency: unpaid balance of ISSUED invoices (VERIFIED allocations only)."""

    currency: str
    outstanding: Decimal
    overdue: Decimal  # part of `outstanding` on invoices past their due date (tenant-local today)
    open_invoices: int
    overdue_invoices: int


def verified_paid_subquery() -> ScalarSelect[Decimal]:
    """Verified money allocated to the outer TenantHireInvoice (the same paid amount as `verified_paid`)."""
    return (
        select(func.coalesce(func.sum(HirePaymentAllocation.amount), 0))
        .join(CustomerPayment, CustomerPayment.id == HirePaymentAllocation.payment_id)
        .where(
            HirePaymentAllocation.invoice_id == TenantHireInvoice.id,
            HirePaymentAllocation.released_at.is_(None),
            CustomerPayment.status == SettlementStatus.VERIFIED,
        )
        .scalar_subquery()
    )


def overdue_conditions(today: date) -> tuple[ColumnElement[bool], ...]:
    """Issued, not fully paid by verified money, and due before `today` (the tenant's local date): the one
    definition behind the dashboard's overdue figures and the invoice list's `overdue` filter."""
    return (
        TenantHireInvoice.status == HireInvoiceStatus.ISSUED,
        TenantHireInvoice.total > verified_paid_subquery(),
        TenantHireInvoice.due_date < today,
    )


def open_receivables(session: Session, today: date) -> list[ReceivableTotals]:
    """Tenant-wide (RLS-scoped) open receivables per currency; the same paid amount as `verified_paid`."""
    paid = verified_paid_subquery()
    rows = session.execute(
        select(TenantHireInvoice.currency, TenantHireInvoice.due_date, TenantHireInvoice.total - paid).where(
            TenantHireInvoice.status == HireInvoiceStatus.ISSUED, TenantHireInvoice.total > paid
        )
    ).tuples()
    acc: dict[str, list[Decimal]] = {}
    for currency, due, balance in rows:
        t = acc.setdefault(currency, [ZERO, ZERO, ZERO, ZERO])
        late = due is not None and due < today
        t[0] += balance
        t[1] += balance if late else ZERO
        t[2] += 1
        t[3] += 1 if late else 0
    return [ReceivableTotals(c, t[0], t[1], int(t[2]), int(t[3])) for c, t in sorted(acc.items())]


Entry = tuple[datetime, Kind, str, str, Decimal, Decimal]  # at, kind, reference, description, debit, credit


class ReceivablesService:
    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self._s, self._tid = session, tenant_id

    def _customer(self, customer_id: uuid.UUID) -> Customer:
        customer = self._s.get(Customer, customer_id)
        if customer is None:
            raise NotFound("Customer not found")
        return customer

    def _sum(self, stmt: Executable) -> Decimal:
        return Decimal(self._s.execute(stmt).scalar_one())

    def balances(self, customer_id: uuid.UUID) -> list[CustomerBalanceDto]:
        self._customer(customer_id)
        currencies = {
            *self._s.execute(
                select(TenantHireInvoice.currency).where(TenantHireInvoice.customer_id == customer_id)
            ).scalars(),
            *self._s.execute(
                select(CustomerPayment.currency).where(CustomerPayment.customer_id == customer_id)
            ).scalars(),
        } or {tenant_settings(self._s, self._tid).currency}
        return [self._balance(customer_id, c) for c in sorted(currencies)]

    def _balance(self, customer_id: uuid.UUID, currency: str) -> CustomerBalanceDto:
        inv = (TenantHireInvoice.customer_id == customer_id, TenantHireInvoice.currency == currency)
        pay = (CustomerPayment.customer_id == customer_id, CustomerPayment.currency == currency)
        invoiced = self._sum(
            select(func.coalesce(func.sum(TenantHireInvoice.total), 0)).where(
                *inv, TenantHireInvoice.issued_at.is_not(None)
            )
        )
        reversed_ = self._sum(
            select(func.coalesce(func.sum(FinancialAdjustment.amount), 0)).where(
                FinancialAdjustment.customer_id == customer_id, FinancialAdjustment.currency == currency
            )
        )
        verified = self._sum(
            select(func.coalesce(func.sum(CustomerPayment.amount), 0)).where(
                *pay, CustomerPayment.status == SettlementStatus.VERIFIED
            )
        )
        claimed = self._sum(
            select(func.coalesce(func.sum(CustomerPayment.amount), 0)).where(
                *pay, CustomerPayment.status == SettlementStatus.CLAIMED
            )
        )
        allocated = self._sum(
            select(func.coalesce(func.sum(HirePaymentAllocation.amount), 0))
            .join(CustomerPayment, CustomerPayment.id == HirePaymentAllocation.payment_id)
            .where(
                *pay, CustomerPayment.status == SettlementStatus.VERIFIED, HirePaymentAllocation.released_at.is_(None)
            )
        )
        issued = self._s.execute(
            select(TenantHireInvoice).where(*inv, TenantHireInvoice.status == HireInvoiceStatus.ISSUED)
        ).scalars()
        open_count = sum(1 for i in issued if i.total - verified_paid(self._s, i.id) > 0)
        return CustomerBalanceDto(
            customer_id=customer_id,
            currency=currency,
            invoiced=invoiced,
            reversed=reversed_,
            verified_payments=verified,
            balance=invoiced - reversed_ - verified,
            unallocated_credit=verified - allocated,
            claimed_unverified=claimed,
            open_invoices=open_count,
        )

    def _entries(self, customer_id: uuid.UUID, currency: str, end: datetime) -> list[Entry]:
        out: list[Entry] = []
        for i in self._s.execute(
            select(TenantHireInvoice).where(
                TenantHireInvoice.customer_id == customer_id,
                TenantHireInvoice.currency == currency,
                TenantHireInvoice.issued_at < end,
            )
        ).scalars():
            assert i.issued_at is not None and i.invoice_number is not None
            out.append((i.issued_at, "INVOICE", i.invoice_number, "Hire invoice", i.total, ZERO))
        numbers = dict(
            self._s.execute(
                select(TenantHireInvoice.id, TenantHireInvoice.invoice_number).where(
                    TenantHireInvoice.customer_id == customer_id
                )
            )
            .tuples()
            .all()
        )
        for a in self._s.execute(
            select(FinancialAdjustment).where(
                FinancialAdjustment.customer_id == customer_id,
                FinancialAdjustment.currency == currency,
                FinancialAdjustment.created_at < end,
            )
        ).scalars():
            ref = numbers.get(a.invoice_id) if a.invoice_id else None
            out.append((a.created_at, "REVERSAL", ref or str(a.id), f"Reversal: {a.reason}"[:200], ZERO, a.amount))
        for p in self._s.execute(
            select(CustomerPayment).where(
                CustomerPayment.customer_id == customer_id,
                CustomerPayment.currency == currency,
                CustomerPayment.status == SettlementStatus.VERIFIED,
                CustomerPayment.received_at < end,
            )
        ).scalars():
            ref = p.reference or f"{p.method.value}-{str(p.id)[:8]}"
            out.append((p.received_at, "PAYMENT", ref, f"{p.method.value} payment (verified)", ZERO, p.amount))
        return sorted(out, key=lambda e: (e[0], e[1]))

    def statement(self, customer_id: uuid.UUID, currency: str | None, first: date, last: date) -> CustomerStatementDto:
        self._customer(customer_id)
        settings = tenant_settings(self._s, self._tid)
        currency = currency or settings.currency
        start, end = local_bounds(settings.timezone, first, last)
        entries = self._entries(customer_id, currency, end)
        opening = sum((e[4] - e[5] for e in entries if e[0] < start), ZERO)
        running, lines = opening, []
        for at, kind, ref, desc, debit, credit in (e for e in entries if e[0] >= start):
            running += debit - credit
            lines.append(
                StatementLineDto(
                    at=at,
                    kind=kind,
                    reference=ref,
                    description=desc,
                    debit=debit,
                    credit=credit,
                    running_balance=running,
                )
            )
        claims = list(
            self._s.execute(
                select(CustomerPayment)
                .where(
                    CustomerPayment.customer_id == customer_id,
                    CustomerPayment.currency == currency,
                    CustomerPayment.status == SettlementStatus.CLAIMED,
                    CustomerPayment.received_at < end,
                )
                .order_by(CustomerPayment.received_at)
            ).scalars()
        )
        return CustomerStatementDto(
            customer_id=customer_id,
            currency=currency,
            period_from=first,
            period_to=last,
            opening_balance=opening,
            lines=lines,
            total_debits=sum((line.debit for line in lines), ZERO),
            total_credits=sum((line.credit for line in lines), ZERO),
            closing_balance=running,
            claimed_unverified=[payment_dto(self._s, p) for p in claims],
            claimed_unverified_total=sum((p.amount for p in claims), ZERO),
        )
