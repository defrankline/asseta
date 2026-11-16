"""Customer hours per customer (ADR-008: what owners read): bought, activated, used, left, awaiting activation and the
credit still owed on credit invoices. Derived from the orders, the hours ledger and the invoices on every read."""

import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.modules.hours.credit_invoices import invoice_dtos, invoice_query, local_today
from asseta.modules.hours.dto import CustomerHoursSummaryDto
from asseta.modules.hours.ledger import ZERO
from asseta.modules.hours.models import HoursPurchase
from asseta.modules.hours.service import balances


def customer_hours(
    session: Session, tenant_id: uuid.UUID, now: datetime, customer_id: uuid.UUID | None = None
) -> list[CustomerHoursSummaryDto]:
    acc: dict[uuid.UUID, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    for b in balances(session, customer_id=customer_id):
        row = acc[b.customer_id]
        row["activated"] += b.activated
        row["used"] += b.consumed + b.provisional
        row["left"] += b.remaining
        row["awaiting"] += b.awaiting_activation
    stmt = (
        select(HoursPurchase.customer_id, func.sum(HoursPurchase.hours))
        .where(HoursPurchase.cancelled_at.is_(None))
        .group_by(HoursPurchase.customer_id)
    )
    if customer_id is not None:
        stmt = stmt.where(HoursPurchase.customer_id == customer_id)
    for cid, hours in session.execute(stmt).tuples():
        acc[cid]["bought"] += Decimal(hours)
    owed: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    open_invoices = list(
        session.execute(invoice_query(local_today(session, tenant_id, now), customer_id=customer_id, open_only=True))
        .scalars()
        .all()
    )
    for inv in invoice_dtos(session, tenant_id, now, open_invoices, with_payments=False):
        owed[inv.customer_id] += inv.balance
        acc[inv.customer_id]  # a customer who owes credit shows up even with nothing left
    return [
        CustomerHoursSummaryDto(
            customer_id=cid,
            bought=v["bought"],
            activated=v["activated"],
            used=v["used"],
            left=v["left"],
            awaiting_activation=v["awaiting"],
            credit_owed=owed[cid],
        )
        for cid, v in acc.items()
    ]
