"""Recomputation of petty cash fund balances (DEC-033, see balance_checks). Every fund's ledger is recomputed; the
figures stored when something was recorded (a count's expected cash, an approved fund adjustment's resulting balance)
are compared only while nothing later touched the fund, as with custody snapshots."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.modules.adjustments.models import AdjustmentEntryStatus, AdjustmentLedgerEntry, AdjustmentType
from asseta.modules.dataprotection.balance_report import CheckKind, Finding, Report, differs
from asseta.modules.expenses.models import Expense
from asseta.modules.finance.custody_models import CashVariance
from asseta.modules.pettycash.ledger import FundLedger
from asseta.modules.pettycash.models import (
    PettyCashAdjustment,
    PettyCashAdvance,
    PettyCashCount,
    PettyCashFund,
    PettyCashMovement,
)


def _last_activity(s: Session, fund: PettyCashFund) -> datetime | None:
    stamps: list[Any] = [
        select(
            func.max(
                func.greatest(
                    PettyCashMovement.created_at,
                    PettyCashMovement.decided_at,
                    PettyCashMovement.issued_at,
                    PettyCashMovement.received_at,
                )
            )
        ).where(PettyCashMovement.fund_id == fund.id),
        select(func.max(func.greatest(Expense.submitted_at, Expense.decided_at))).where(
            Expense.petty_cash_fund_id == fund.id
        ),
        select(func.max(func.greatest(PettyCashAdjustment.created_at, PettyCashAdjustment.decided_at))).where(
            PettyCashAdjustment.fund_id == fund.id
        ),
        select(func.max(func.greatest(PettyCashAdvance.issued_at, PettyCashAdvance.cleared_at))).where(
            PettyCashAdvance.fund_id == fund.id
        ),
        select(func.max(func.greatest(CashVariance.opened_at, CashVariance.resolved_at))).where(
            CashVariance.petty_cash_fund_id == fund.id
        ),
    ]
    values = [v for q in stamps if (v := s.execute(q).scalar()) is not None]
    return max(values) if values else None


def check_petty_cash(s: Session, r: Report, now: datetime) -> None:
    ledger = FundLedger(s, now)
    for fund in s.execute(select(PettyCashFund).order_by(PettyCashFund.code)).scalars():
        figures = ledger.figures(fund)
        r.checked[CheckKind.PETTY_CASH_FUND] += 1
        last = _last_activity(s, fund)
        count = s.execute(
            select(PettyCashCount)
            .where(PettyCashCount.fund_id == fund.id)
            .order_by(PettyCashCount.counted_at.desc(), PettyCashCount.id)
            .limit(1)
        ).scalar_one_or_none()
        if count is not None and (last is None or last <= count.counted_at):
            r.checked[CheckKind.PETTY_CASH_FUND] += 1
            # the count's own difference is a variance opened at the same instant; its write-off would come later
            if differs(figures.available, count.expected_amount):
                r.findings.append(
                    Finding(
                        CheckKind.PETTY_CASH_FUND,
                        "petty_cash_fund",
                        str(fund.id),
                        f"{fund.code} {fund.name}",
                        figures.available,
                        count.expected_amount,
                        fund.currency,
                        f"count {count.number} expected cash",
                        {"fund_id": str(fund.id), "count_id": str(count.id)},
                    )
                )
        entry = s.execute(
            select(AdjustmentLedgerEntry)
            .where(
                AdjustmentLedgerEntry.adjustment_type == AdjustmentType.PETTY_CASH_ADJUSTMENT,
                AdjustmentLedgerEntry.original_id == fund.id,
                AdjustmentLedgerEntry.status == AdjustmentEntryStatus.APPROVED,
                AdjustmentLedgerEntry.resulting_balance.is_not(None),
            )
            .order_by(AdjustmentLedgerEntry.posted_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if entry is not None and entry.resulting_balance is not None and (last is None or last <= entry.posted_at):
            r.checked[CheckKind.PETTY_CASH_FUND] += 1
            if differs(figures.balance, entry.resulting_balance):
                r.findings.append(
                    Finding(
                        CheckKind.PETTY_CASH_FUND,
                        "petty_cash_fund",
                        str(fund.id),
                        f"{fund.code} {fund.name}",
                        figures.balance,
                        entry.resulting_balance,
                        fund.currency,
                        f"adjustment {entry.id} resulting balance",
                        {"fund_id": str(fund.id)},
                    )
                )
