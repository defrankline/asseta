"""Recomputation of cash per custodian, customer receivables and credit invoices (see balance_checks)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from asseta.modules.adjustments.models import AdjustmentEntryStatus, AdjustmentLedgerEntry, AdjustmentUnit
from asseta.modules.customers.models import Customer
from asseta.modules.dataprotection.balance_report import ZERO, CheckKind, Finding, Report, differs, system_ctx
from asseta.modules.expenses.models import Expense
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.custody_models import CashTransfer, CustodyAdjustment
from asseta.modules.finance.models import CashHandover, CustomerPayment, SettlementStatus, SupervisorCashCustody
from asseta.modules.finance.receivables import ReceivablesService
from asseta.modules.fleet.models import StaffMember
from asseta.modules.hours.models import CreditInvoice, CreditInvoicePayment, HoursPurchase

# --- cash per custodian --------------------------------------------------------------------------------------------
CUSTODIANS = """
SELECT staff_member_id FROM supervisor_cash_custody UNION SELECT received_by_staff_id FROM customer_payment
UNION SELECT staff_member_id FROM cash_handover UNION SELECT from_staff_id FROM cash_transfer
UNION SELECT to_staff_id FROM cash_transfer UNION SELECT staff_member_id FROM custody_adjustment
UNION SELECT custodian_staff_id FROM expense
"""


def _later_custody_activity(s: Session, staff_id: uuid.UUID, currency: str, after: datetime) -> bool:
    stamps: list[Any] = [
        select(func.max(SupervisorCashCustody.created_at)).where(
            SupervisorCashCustody.staff_member_id == staff_id, SupervisorCashCustody.currency == currency
        ),
        select(func.max(func.greatest(CashHandover.recorded_at, CashHandover.verified_at))).where(
            CashHandover.staff_member_id == staff_id, CashHandover.currency == currency
        ),
        select(func.max(func.greatest(CashTransfer.recorded_at, CashTransfer.acknowledged_at))).where(
            or_(CashTransfer.from_staff_id == staff_id, CashTransfer.to_staff_id == staff_id),
            CashTransfer.currency == currency,
        ),
        select(
            func.max(
                func.greatest(CustomerPayment.recorded_at, CustomerPayment.verified_at, CustomerPayment.reversed_at)
            )
        ).where(CustomerPayment.received_by_staff_id == staff_id, CustomerPayment.currency == currency),
        select(func.max(func.greatest(CustodyAdjustment.created_at, CustodyAdjustment.decided_at))).where(
            CustodyAdjustment.staff_member_id == staff_id, CustodyAdjustment.currency == currency
        ),
        select(func.max(func.greatest(Expense.submitted_at, Expense.decided_at))).where(
            Expense.custodian_staff_id == staff_id, Expense.currency == currency
        ),
    ]
    return any((latest := s.execute(q).scalar()) is not None and latest > after for q in stamps)


def check_cash(s: Session, r: Report, now: datetime) -> None:
    service = CashCustodyService(s, system_ctx(r.tenant_id), now)
    staff_ids = [cast(uuid.UUID, i) for i in s.execute(text(CUSTODIANS)).scalars() if i is not None]
    outstanding: dict[tuple[uuid.UUID, str], Decimal] = {}
    for staff_id in staff_ids:
        for balance in service.balances(staff_id):
            r.checked[CheckKind.CASH_CUSTODY] += 1
            outstanding[(staff_id, balance.currency)] = balance.outstanding
    latest_snapshot: dict[tuple[uuid.UUID, str], AdjustmentLedgerEntry] = {}
    for e in s.execute(
        select(AdjustmentLedgerEntry)
        .where(
            AdjustmentLedgerEntry.unit == AdjustmentUnit.MONEY,
            AdjustmentLedgerEntry.staff_member_id.is_not(None),
            AdjustmentLedgerEntry.resulting_balance.is_not(None),
            AdjustmentLedgerEntry.status == AdjustmentEntryStatus.APPROVED,
        )
        .order_by(AdjustmentLedgerEntry.posted_at)
    ).scalars():
        assert e.staff_member_id is not None and e.currency is not None
        latest_snapshot[(e.staff_member_id, e.currency)] = e
    for (staff_id, currency), e in latest_snapshot.items():
        stored = e.resulting_balance
        ledger = outstanding.get((staff_id, currency), ZERO)
        if stored is None or _later_custody_activity(s, staff_id, currency, e.posted_at):
            continue
        r.checked[CheckKind.CASH_CUSTODY] += 1
        if differs(ledger, stored):
            staff = s.get(StaffMember, staff_id)
            r.findings.append(
                Finding(
                    CheckKind.CASH_CUSTODY,
                    "staff_member",
                    str(staff_id),
                    staff.full_name if staff else str(staff_id),
                    ledger,
                    stored,
                    currency,
                    f"adjustment {e.id} resulting balance",
                    {"staff_member_id": str(staff_id)},
                )
            )


# --- customer receivables ------------------------------------------------------------------------------------------
def _recompute_receivable(s: Session, customer_id: uuid.UUID, currency: str) -> Decimal:
    """Credit invoices of orders not cancelled, less their verified (not reversed) payments, straight from the rows."""
    invoiced = Decimal(
        s.execute(
            select(func.coalesce(func.sum(CreditInvoice.amount), 0))
            .join(HoursPurchase, HoursPurchase.id == CreditInvoice.purchase_id)
            .where(
                CreditInvoice.customer_id == customer_id,
                CreditInvoice.currency == currency,
                HoursPurchase.cancelled_at.is_(None),
            )
        ).scalar_one()
    )
    paid = Decimal(
        s.execute(
            select(func.coalesce(func.sum(CreditInvoicePayment.amount), 0))
            .join(CreditInvoice, CreditInvoice.id == CreditInvoicePayment.invoice_id)
            .join(HoursPurchase, HoursPurchase.id == CreditInvoice.purchase_id)
            .join(CustomerPayment, CustomerPayment.id == CreditInvoicePayment.payment_id)
            .where(
                CreditInvoice.customer_id == customer_id,
                CreditInvoice.currency == currency,
                HoursPurchase.cancelled_at.is_(None),
                CustomerPayment.status == SettlementStatus.VERIFIED,
                CustomerPayment.reversed_at.is_(None),
            )
        ).scalar_one()
    )
    return invoiced - paid


def check_receivables(s: Session, r: Report) -> None:
    service = ReceivablesService(s, r.tenant_id)
    customers = s.execute(select(Customer)).scalars().all()
    names = {c.id: c.name for c in customers}
    for customer in customers:
        for balance in service.balances(customer.id):
            r.checked[CheckKind.CUSTOMER_RECEIVABLE] += 1
            recomputed = _recompute_receivable(s, customer.id, balance.currency)
            if differs(recomputed, balance.balance):
                r.findings.append(
                    Finding(
                        CheckKind.CUSTOMER_RECEIVABLE,
                        "customer",
                        str(customer.id),
                        names.get(customer.id, str(customer.id)),
                        recomputed,
                        balance.balance,
                        balance.currency,
                        "displayed balance",
                        {"customer_id": str(customer.id)},
                    )
                )


def check_invoices(s: Session, r: Report) -> None:
    """A credit invoice never asks for more than its order costs."""
    for inv, order_amount in s.execute(
        select(CreditInvoice, HoursPurchase.amount).join(HoursPurchase, HoursPurchase.id == CreditInvoice.purchase_id)
    ).tuples():
        r.checked[CheckKind.INVOICE_TOTAL] += 1
        if inv.amount > order_amount + ZERO:
            r.findings.append(
                Finding(
                    CheckKind.INVOICE_TOTAL,
                    "credit_invoice",
                    str(inv.id),
                    inv.invoice_number,
                    order_amount,
                    inv.amount,
                    inv.currency,
                    "credit invoice amount against its order",
                    {"purchase_id": str(inv.purchase_id)},
                )
            )
