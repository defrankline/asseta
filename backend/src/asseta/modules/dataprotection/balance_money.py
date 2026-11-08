"""Recomputation of cash per custodian, customer receivables and invoice totals (see balance_checks)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from asseta.modules.adjustments.models import (
    AdjustmentEntryStatus,
    AdjustmentLedgerEntry,
    AdjustmentType,
    AdjustmentUnit,
)
from asseta.modules.dataprotection.balance_report import ZERO, CheckKind, Finding, Report, differs, system_ctx
from asseta.modules.expenses.models import Expense
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.custody_models import CashTransfer, CustodyAdjustment
from asseta.modules.finance.models import (
    CREDIT_KINDS,
    DEBIT_KINDS,
    CashHandover,
    CustomerPayment,
    FinancialAdjustment,
    HireInvoiceLine,
    HireInvoiceStatus,
    SettlementStatus,
    SupervisorCashCustody,
    TenantHireInvoice,
)
from asseta.modules.finance.receivables import ReceivablesService
from asseta.modules.fleet.models import StaffMember
from asseta.modules.jobs.models import Customer

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
    inv = (TenantHireInvoice.customer_id == customer_id, TenantHireInvoice.currency == currency)
    pay = (CustomerPayment.customer_id == customer_id, CustomerPayment.currency == currency)
    adj = (FinancialAdjustment.customer_id == customer_id, FinancialAdjustment.currency == currency)

    def total(column: Any, *conds: Any) -> Decimal:
        return Decimal(s.execute(select(func.coalesce(func.sum(column), 0)).where(*conds)).scalar_one())

    invoiced = total(TenantHireInvoice.total, *inv, TenantHireInvoice.issued_at.is_not(None))
    credits_ = total(FinancialAdjustment.amount, *adj, FinancialAdjustment.kind.in_(CREDIT_KINDS))
    debits = total(FinancialAdjustment.amount, *adj, FinancialAdjustment.kind.in_(DEBIT_KINDS))
    verified = total(CustomerPayment.amount, *pay, CustomerPayment.status == SettlementStatus.VERIFIED)
    return invoiced - credits_ - verified + debits


def _later_receivable_activity(s: Session, customer_id: uuid.UUID, currency: str, after: datetime) -> bool:
    stamps: list[Any] = [
        select(
            func.max(
                func.greatest(TenantHireInvoice.created_at, TenantHireInvoice.issued_at, TenantHireInvoice.voided_at)
            )
        ).where(TenantHireInvoice.customer_id == customer_id, TenantHireInvoice.currency == currency),
        select(
            func.max(
                func.greatest(CustomerPayment.recorded_at, CustomerPayment.verified_at, CustomerPayment.reversed_at)
            )
        ).where(CustomerPayment.customer_id == customer_id, CustomerPayment.currency == currency),
        select(func.max(FinancialAdjustment.created_at)).where(
            FinancialAdjustment.customer_id == customer_id, FinancialAdjustment.currency == currency
        ),
    ]
    return any((latest := s.execute(q).scalar()) is not None and latest > after for q in stamps)


def check_receivables(s: Session, r: Report) -> None:
    service = ReceivablesService(s, r.tenant_id)
    customers = s.execute(select(Customer)).scalars().all()
    names = {c.id: c.name for c in customers}
    latest_snapshot: dict[tuple[uuid.UUID, str], AdjustmentLedgerEntry] = {}
    for e in s.execute(
        select(AdjustmentLedgerEntry)
        .where(
            AdjustmentLedgerEntry.adjustment_type == AdjustmentType.INVOICE_VOID,
            AdjustmentLedgerEntry.customer_id.is_not(None),
            AdjustmentLedgerEntry.resulting_balance.is_not(None),
            AdjustmentLedgerEntry.status == AdjustmentEntryStatus.APPROVED,
        )
        .order_by(AdjustmentLedgerEntry.posted_at)
    ).scalars():
        assert e.customer_id is not None and e.currency is not None
        latest_snapshot[(e.customer_id, e.currency)] = e
    for customer in customers:
        for balance in service.balances(customer.id):
            r.checked[CheckKind.CUSTOMER_RECEIVABLE] += 1
            recomputed = _recompute_receivable(s, customer.id, balance.currency)
            if differs(recomputed, balance.balance):
                r.findings.append(
                    _receivable_finding(
                        customer.id, names, balance.currency, recomputed, balance.balance, "displayed balance"
                    )
                )
            snapshot = latest_snapshot.get((customer.id, balance.currency))
            if (
                snapshot is not None
                and snapshot.resulting_balance is not None
                and not _later_receivable_activity(s, customer.id, balance.currency, snapshot.posted_at)
                and differs(recomputed, snapshot.resulting_balance)
            ):
                r.findings.append(
                    _receivable_finding(
                        customer.id,
                        names,
                        balance.currency,
                        recomputed,
                        snapshot.resulting_balance,
                        f"adjustment {snapshot.id} resulting balance",
                    )
                )


def _receivable_finding(
    customer_id: uuid.UUID, names: dict[uuid.UUID, str], currency: str, ledger: Decimal, stored: Decimal, source: str
) -> Finding:
    return Finding(
        CheckKind.CUSTOMER_RECEIVABLE,
        "customer",
        str(customer_id),
        names.get(customer_id, str(customer_id)),
        ledger,
        stored,
        currency,
        source,
        {"customer_id": str(customer_id)},
    )


def check_invoices(s: Session, r: Report) -> None:
    line_totals = dict(
        s.execute(
            select(HireInvoiceLine.invoice_id, func.sum(HireInvoiceLine.amount)).group_by(HireInvoiceLine.invoice_id)
        ).all()
    )
    for inv in s.execute(
        select(TenantHireInvoice).where(TenantHireInvoice.status == HireInvoiceStatus.ISSUED)
    ).scalars():
        r.checked[CheckKind.INVOICE_TOTAL] += 1
        lines = Decimal(line_totals.get(inv.id, ZERO))
        arithmetic = inv.subtotal - inv.discount_total + inv.tax_total
        consistent = (not differs(arithmetic, inv.total)) and (
            not differs(lines, inv.total) or not differs(lines, inv.subtotal)
        )
        if not consistent:
            r.findings.append(
                Finding(
                    CheckKind.INVOICE_TOTAL,
                    "tenant_hire_invoice",
                    str(inv.id),
                    inv.invoice_number or str(inv.id),
                    lines,
                    inv.total,
                    inv.currency,
                    "invoice total against its lines",
                    {"subtotal": str(inv.subtotal), "discount": str(inv.discount_total), "tax": str(inv.tax_total)},
                )
            )
