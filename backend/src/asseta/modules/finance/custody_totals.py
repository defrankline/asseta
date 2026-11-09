"""Every custodian's current cash in a fixed number of grouped queries, for tenant-wide views. The same figures as
`CashCustodyService.balances` per person (a test holds the two equal); derived from the records, nothing stored."""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from asseta.modules.expenses.models import Expense, ExpensePaidFrom, ExpenseStatus
from asseta.modules.finance.cash_service import SIGN
from asseta.modules.finance.custody_dto import ReconciliationFigure as F
from asseta.modules.finance.custody_models import (
    CashDecisionStatus,
    CashFloatAcknowledgement,
    CashRetention,
    CashTransfer,
    CashTransferStatus,
    CashVariance,
    CustodyAdjustment,
    VarianceOutcome,
)
from asseta.modules.finance.models import (
    CashHandover,
    CustomerPayment,
    HirePaymentMethod,
    SettlementStatus,
    SupervisorCashCustody,
)

ZERO = Decimal(0)
Key = tuple[uuid.UUID, str]


@dataclass(frozen=True)
class CustodianBalance:
    staff_member_id: uuid.UUID
    currency: str
    outstanding: Decimal
    in_transit_out: Decimal
    in_transit_in: Decimal
    claimed_unverified_handovers: Decimal
    pending_floats: Decimal
    pending_spending: Decimal
    approved_retention: Decimal


def all_custody_balances(s: Session, now: datetime) -> list[CustodianBalance]:
    """Current custody per (custodian, currency) with anything to show."""
    totals: dict[Key, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))

    def add(rows: Any, figure: str) -> None:
        for staff_id, currency, amount in rows:
            if staff_id is not None and amount:
                totals[(staff_id, currency)][figure] += Decimal(amount)

    c, ack = SupervisorCashCustody, CashFloatAcknowledgement
    float_row = select(c.staff_member_id, c.currency).outerjoin(ack, ack.custody_entry_id == c.id)
    counted = case(
        (c.ack_required.is_(False), c.amount),
        (and_(ack.id.is_not(None), ack.disputed.is_(False), ack.amount_received > 0), ack.amount_received),
        else_=ZERO,
    )
    group = (c.staff_member_id, c.currency)
    add(s.execute(float_row.add_columns(func.sum(counted)).group_by(*group)), F.FLOATS_ISSUED)
    awaiting = float_row.add_columns(func.sum(c.amount)).where(c.ack_required.is_(True), ack.id.is_(None))
    add(s.execute(awaiting.group_by(*group)), F.PENDING_FLOATS)

    p = CustomerPayment
    add(
        s.execute(
            select(p.received_by_staff_id, p.currency, func.sum(p.amount))
            .where(p.method == HirePaymentMethod.CASH, p.status != SettlementStatus.REJECTED)
            .group_by(p.received_by_staff_id, p.currency)
        ),
        F.COLLECTIONS,
    )

    e = Expense
    for figure, statuses in (
        (F.APPROVED_SPENDING, e.status == ExpenseStatus.APPROVED),
        (F.PENDING_SPENDING, e.status.not_in((ExpenseStatus.APPROVED, ExpenseStatus.REJECTED))),
    ):
        add(
            s.execute(
                select(e.custodian_staff_id, e.currency, func.sum(e.amount))
                .where(e.paid_from == ExpensePaidFrom.CASH_CUSTODY, statuses)
                .group_by(e.custodian_staff_id, e.currency)
            ),
            figure,
        )

    h = CashHandover
    confirmed = func.sum(func.coalesce(h.amount_received, h.amount))
    verified = select(h.staff_member_id, h.currency, confirmed).where(h.status == SettlementStatus.VERIFIED)
    add(s.execute(verified.group_by(h.staff_member_id, h.currency)), F.VERIFIED_HANDOVERS)
    claimed = select(h.staff_member_id, h.currency, func.sum(h.amount)).where(h.status == SettlementStatus.CLAIMED)
    add(s.execute(claimed.group_by(h.staff_member_id, h.currency)), F.CLAIMED_UNVERIFIED_HANDOVERS)

    t = CashTransfer
    done = t.status == CashTransferStatus.ACKNOWLEDGED
    transit = t.status == CashTransferStatus.PENDING_ACKNOWLEDGEMENT
    for party, moved, in_transit in (
        (t.from_staff_id, F.TRANSFERS_OUT, F.IN_TRANSIT_OUT),
        (t.to_staff_id, F.TRANSFERS_IN, F.IN_TRANSIT_IN),
    ):
        add(
            s.execute(select(party, t.currency, func.sum(t.amount_received)).where(done).group_by(party, t.currency)),
            moved,
        )
        add(
            s.execute(
                select(party, t.currency, func.sum(t.amount_declared)).where(transit).group_by(party, t.currency)
            ),
            in_transit,
        )

    a = CustodyAdjustment
    add(
        s.execute(
            select(a.staff_member_id, a.currency, func.sum(a.amount))
            .where(a.status == CashDecisionStatus.APPROVED)
            .group_by(a.staff_member_id, a.currency)
        ),
        F.ADJUSTMENTS,
    )
    v = CashVariance
    add(
        s.execute(
            select(v.staff_member_id, v.currency, func.sum(v.amount))
            .where(v.outcome == VarianceOutcome.WRITTEN_OFF)
            .group_by(v.staff_member_id, v.currency)
        ),
        F.WRITTEN_OFF,
    )

    r = CashRetention
    retained = {
        (staff_id, currency): Decimal(amount)
        for staff_id, currency, amount in s.execute(
            select(r.staff_member_id, r.currency, func.sum(r.amount))
            .where(r.status == CashDecisionStatus.APPROVED, or_(r.valid_until.is_(None), r.valid_until > now))
            .group_by(r.staff_member_id, r.currency)
        )
    }
    return [
        CustodianBalance(
            staff_member_id=staff_id,
            currency=currency,
            outstanding=sum((sign * figures[fig] for fig, sign in SIGN.items()), ZERO),
            in_transit_out=figures[F.IN_TRANSIT_OUT],
            in_transit_in=figures[F.IN_TRANSIT_IN],
            claimed_unverified_handovers=figures[F.CLAIMED_UNVERIFIED_HANDOVERS],
            pending_floats=figures[F.PENDING_FLOATS],
            pending_spending=figures[F.PENDING_SPENDING],
            approved_retention=retained.get((staff_id, currency), ZERO),
        )
        for (staff_id, currency), figures in sorted(totals.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))
    ]
