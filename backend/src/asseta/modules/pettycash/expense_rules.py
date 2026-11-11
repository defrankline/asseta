"""Expenses paid from a petty cash fund (DEC-033 rules 1-3). Called by the expense service, online and at sync, so a
device can never skip a rule: only the holder (or a recorder for them, tenant policy) records; the fund's currency;
an inactive fund is refused; above what is available is refused online and, from offline sync, kept for approval and
flagged OVERSPEND when the tenant allows it; above the per-expense maximum always needs a human approval."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.errors import BusinessRuleViolation, NotFound, PermissionDenied
from asseta.modules.expenses.models import ExpenseFlag
from asseta.modules.finance.custody_rules import cash_policy, may_record_for_others, own_staff
from asseta.modules.identity.principal import RequestContext
from asseta.modules.pettycash.ledger import FundLedger
from asseta.modules.pettycash.models import AdvanceStatus, PettyCashAdvance, PettyCashFund
from asseta.modules.policy.capabilities import PETTY_CASH, require_capability
from asseta.modules.policy.service import PolicyService


@dataclass
class FundExpense:
    fund_id: uuid.UUID
    advance_id: uuid.UUID | None
    currency: str
    available: Decimal
    flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def check_fund_expense(
    session: Session,
    ctx: RequestContext,
    now: datetime,
    *,
    fund_id: uuid.UUID | None,
    advance_id: uuid.UUID | None,
    amount: Decimal,
    currency: str | None,
    base_currency: str,
    source: str,
) -> FundExpense:
    assert ctx.tenant_id is not None
    require_capability(session, ctx.tenant_id, PETTY_CASH, now)
    if fund_id is None:
        raise BusinessRuleViolation("Name the petty cash fund that paid", code="PETTY_CASH_FUND_REQUIRED")
    fund = session.execute(
        select(PettyCashFund).where(PettyCashFund.id == fund_id).with_for_update()
    ).scalar_one_or_none()  # serialises spending from one fund
    if fund is None:
        raise NotFound("Petty cash fund not found", code="PETTY_CASH_FUND_NOT_FOUND")
    if not fund.is_active:
        raise BusinessRuleViolation("This petty cash fund is inactive", code="PETTY_CASH_FUND_INACTIVE")
    if currency is not None and currency != fund.currency:
        raise BusinessRuleViolation(
            f"The fund holds {fund.currency}, not {currency}", code="PETTY_CASH_CURRENCY_MISMATCH"
        )
    own = own_staff(session, ctx)
    for_others = may_record_for_others(ctx, cash_policy(session, ctx.tenant_id, now).policy)
    ledger = FundLedger(session, now)
    advance = None
    if advance_id is not None:
        advance = session.get(PettyCashAdvance, advance_id)
        if advance is None or advance.fund_id != fund.id:
            raise NotFound("Advance not found in this fund", code="PETTY_CASH_ADVANCE_NOT_FOUND")
        if advance.status is not AdvanceStatus.OUTSTANDING:
            raise BusinessRuleViolation("The advance is already cleared", code="PETTY_CASH_ADVANCE_CLEARED")
        parties = {advance.recipient_staff_id, fund.holder_staff_id}
        if not for_others and (own is None or own.id not in parties):
            raise PermissionDenied("Only the advance's recipient records its expenses", code="NOT_FUND_HOLDER")
        approved, pending = ledger.advance_spending(advance.id)
        available = advance.amount - approved - pending
    else:
        if not for_others and (own is None or own.id != fund.holder_staff_id):
            raise PermissionDenied("Only the fund's holder records expenses paid from it", code="NOT_FUND_HOLDER")
        available = ledger.figures(fund).available
    out = FundExpense(fund.id, advance.id if advance else None, fund.currency, available)
    policy = PolicyService(session).petty_cash(ctx.tenant_id, at=now).policy
    if amount > available:
        what = "advance" if advance else "fund"
        if source != "SYNC" or not policy.overspend_allowed_offline:
            raise BusinessRuleViolation(
                f"The {what} has {fund.currency} {available} available", code="PETTY_CASH_INSUFFICIENT"
            )
        out.flags.append(ExpenseFlag.OVERSPEND.value)
        out.reasons.append(f"Recorded offline above what the {what} had available ({fund.currency} {available})")
    maximum = policy.max_expense_amount
    if maximum is not None and fund.currency == base_currency and amount > maximum:
        out.flags.append(ExpenseFlag.ABOVE_PETTY_CASH_MAXIMUM.value)
        out.reasons.append(f"Above the petty cash maximum per expense ({fund.currency} {maximum})")
    return out
