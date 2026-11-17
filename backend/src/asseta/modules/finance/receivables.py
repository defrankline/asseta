"""Customer balances and statements, per currency (never mixed), on credit invoices (ADR-008 §1): what a customer owes
is the unpaid part of their credit invoices. Only VERIFIED payments (not reversed) move the balance; claimed payments
are reported separately. Credit invoices of cancelled orders owe nothing."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import ColumnElement, ScalarSelect, and_, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Executable

from asseta.core.errors import NotFound
from asseta.modules.customers.models import Customer
from asseta.modules.finance.common import ZERO, local_bounds, tenant_settings
from asseta.modules.finance.dto import CustomerBalanceDto, CustomerStatementDto, StatementLineDto
from asseta.modules.finance.models import AdjustmentKind, CustomerPayment, FinancialAdjustment, SettlementStatus
from asseta.modules.finance.payment_service import payment_dto
from asseta.modules.hours.models import CreditInvoice, CreditInvoicePayment, HoursPaymentAllocation, HoursPurchase

Kind = Literal["INVOICE", "PAYMENT"]


@dataclass(frozen=True)
class ReceivableTotals:
    """Open customer receivables in one currency: unpaid balance of credit invoices (VERIFIED payments only)."""

    currency: str
    outstanding: Decimal
    overdue: Decimal  # part of `outstanding` on invoices past their due date (tenant-local today)
    open_invoices: int
    overdue_invoices: int


def _verified() -> ColumnElement[bool]:
    return and_(CustomerPayment.status == SettlementStatus.VERIFIED, CustomerPayment.reversed_at.is_(None))


def verified_paid_subquery() -> ScalarSelect[Decimal]:
    """Correlated: verified money paid against the outer CreditInvoice."""
    return (
        select(func.coalesce(func.sum(CreditInvoicePayment.amount), 0))
        .join(CustomerPayment, CustomerPayment.id == CreditInvoicePayment.payment_id)
        .where(CreditInvoicePayment.invoice_id == CreditInvoice.id, _verified())
        .scalar_subquery()
    )


def _open_invoices() -> tuple[ColumnElement[bool], ...]:
    """Credit invoices whose order is not cancelled and whose credit was not rejected."""
    return (
        HoursPurchase.id == CreditInvoice.purchase_id,
        HoursPurchase.cancelled_at.is_(None),
        CreditInvoice.rejected_at.is_(None),
    )


def open_receivables(session: Session, today: date) -> list[ReceivableTotals]:
    """Tenant-wide (RLS-scoped) open receivables per currency."""
    paid = verified_paid_subquery()
    rows = session.execute(
        select(CreditInvoice.currency, CreditInvoice.due_date, CreditInvoice.amount - paid)
        .join(HoursPurchase, HoursPurchase.id == CreditInvoice.purchase_id)
        .where(HoursPurchase.cancelled_at.is_(None), CreditInvoice.rejected_at.is_(None), CreditInvoice.amount > paid)
    ).tuples()
    acc: dict[str, list[Decimal]] = {}
    for currency, due, balance in rows:
        t = acc.setdefault(currency, [ZERO, ZERO, ZERO, ZERO])
        late = due < today
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
            *self._s.execute(select(CreditInvoice.currency).where(CreditInvoice.customer_id == customer_id)).scalars(),
            *self._s.execute(
                select(CustomerPayment.currency).where(CustomerPayment.customer_id == customer_id)
            ).scalars(),
        } or {tenant_settings(self._s, self._tid).currency}
        return [self._balance(customer_id, c) for c in sorted(currencies)]

    def balance_of(self, customer_id: uuid.UUID, currency: str) -> CustomerBalanceDto:
        """One customer's balance in one currency (what an adjustment records as its resulting balance)."""
        return self._balance(customer_id, currency)

    def _balance(self, customer_id: uuid.UUID, currency: str) -> CustomerBalanceDto:
        inv = (CreditInvoice.customer_id == customer_id, CreditInvoice.currency == currency, *_open_invoices())
        pay = (CustomerPayment.customer_id == customer_id, CustomerPayment.currency == currency)
        invoiced = self._sum(select(func.coalesce(func.sum(CreditInvoice.amount), 0)).where(*inv))
        paid = self._sum(
            select(func.coalesce(func.sum(CreditInvoicePayment.amount), 0))
            .join(CustomerPayment, CustomerPayment.id == CreditInvoicePayment.payment_id)
            .join(CreditInvoice, CreditInvoice.id == CreditInvoicePayment.invoice_id)
            .where(*inv, _verified())
        )
        verified = self._sum(select(func.coalesce(func.sum(CustomerPayment.amount), 0)).where(*pay, _verified()))
        claimed = self._sum(
            select(func.coalesce(func.sum(CustomerPayment.amount), 0)).where(
                *pay, CustomerPayment.status == SettlementStatus.CLAIMED
            )
        )
        linked = self._sum(  # verified money linked to orders (credit-invoice payments are linked to theirs too)
            select(func.coalesce(func.sum(HoursPaymentAllocation.amount), 0))
            .join(CustomerPayment, CustomerPayment.id == HoursPaymentAllocation.payment_id)
            .where(*pay, _verified(), HoursPaymentAllocation.released_at.is_(None))
        )
        paid_out = self._sum(  # refunds paid back to the customer are no longer their credit (DEC-032 B4)
            select(func.coalesce(func.sum(FinancialAdjustment.amount), 0)).where(
                FinancialAdjustment.customer_id == customer_id,
                FinancialAdjustment.currency == currency,
                FinancialAdjustment.kind == AdjustmentKind.HOURS_REFUND_PAYOUT,
            )
        )
        paid_sub = verified_paid_subquery()
        unpaid = select(func.count()).select_from(CreditInvoice).where(*inv, CreditInvoice.amount > paid_sub)
        open_count = int(self._s.execute(unpaid).scalar_one())
        return CustomerBalanceDto(
            customer_id=customer_id,
            currency=currency,
            invoiced=invoiced,
            verified_payments=paid,
            balance=invoiced - paid,
            unallocated_credit=max(ZERO, verified - linked - paid_out),
            claimed_unverified=claimed,
            open_invoices=open_count,
        )

    def _entries(self, customer_id: uuid.UUID, currency: str, end: datetime) -> list[Entry]:
        out: list[Entry] = []
        invoices = list(
            self._s.execute(
                select(CreditInvoice).where(
                    CreditInvoice.customer_id == customer_id,
                    CreditInvoice.currency == currency,
                    CreditInvoice.issued_at < end,
                    *_open_invoices(),
                )
            ).scalars()
        )
        numbers = {i.id: i.invoice_number for i in invoices}
        for i in invoices:
            out.append((i.issued_at, "INVOICE", i.invoice_number, "Credit invoice", i.amount, ZERO))
        if numbers:
            for link, p in self._s.execute(
                select(CreditInvoicePayment, CustomerPayment)
                .join(CustomerPayment, CustomerPayment.id == CreditInvoicePayment.payment_id)
                .where(
                    CreditInvoicePayment.invoice_id.in_(numbers),
                    _verified(),
                    CustomerPayment.received_at < end,
                )
            ).tuples():
                ref = p.reference or p.collection_number
                text_ = f"{p.method.value} payment of {numbers[link.invoice_id]} (verified)"
                out.append((p.received_at, "PAYMENT", ref, text_, ZERO, link.amount))
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
