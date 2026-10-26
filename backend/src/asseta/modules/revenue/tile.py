"""Accountability dashboard tile for revenue reconciliation (DEC-031 R3): revenue differences still to explain or
decide, per currency, with the oldest open one and the latest items (links to the records and the daily sheet)."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.modules.fleet.models import Machine
from asseta.modules.identity.principal import RequestContext
from asseta.modules.revenue.models import RevenueDifference, RevenueDifferenceStatus

PENDING = (RevenueDifferenceStatus.OPEN, RevenueDifferenceStatus.EXPLANATION_PROPOSED)
WINDOW_DAYS = 30


def revenue_differences_tile(s: Session, _: RequestContext, now: datetime) -> dict[str, Any]:
    counts = dict(
        s.execute(
            select(RevenueDifference.status, func.count())
            .where(RevenueDifference.status.in_(PENDING))
            .group_by(RevenueDifference.status)
        ).all()
    )
    amounts = [
        {"currency": c, "count": int(n), "amount": str(a or Decimal(0))}
        for c, n, a in s.execute(
            select(RevenueDifference.currency, func.count(), func.sum(RevenueDifference.difference))
            .where(RevenueDifference.status.in_(PENDING))
            .group_by(RevenueDifference.currency)
            .order_by(RevenueDifference.currency)
        ).all()
    ]
    oldest = s.execute(
        select(func.min(RevenueDifference.opened_at)).where(RevenueDifference.status == RevenueDifferenceStatus.OPEN)
    ).scalar_one()
    since = now - timedelta(days=WINDOW_DAYS)
    decided = dict(
        s.execute(
            select(RevenueDifference.status, func.count())
            .where(
                RevenueDifference.status.not_in(PENDING),
                RevenueDifference.decided_at >= since,
            )
            .group_by(RevenueDifference.status)
        ).all()
    )
    items = [
        {
            "id": str(r.id),
            "machine_id": str(r.machine_id),
            "machine_code": code,
            "period_key": r.period_key,
            "local_from": r.local_from.isoformat(),
            "local_to": r.local_to.isoformat(),
            "currency": r.currency,
            "difference": str(r.difference),
            "status": r.status.value,
        }
        for r, code in s.execute(
            select(RevenueDifference, Machine.asset_code)
            .join(Machine, Machine.id == RevenueDifference.machine_id)
            .where(RevenueDifference.status.in_(PENDING))
            .order_by(RevenueDifference.opened_at.desc())
            .limit(20)
        ).all()
    ]
    return {
        "open": int(counts.get(RevenueDifferenceStatus.OPEN, 0)),
        "awaiting_decision": int(counts.get(RevenueDifferenceStatus.EXPLANATION_PROPOSED, 0)),
        "amounts": amounts,
        "oldest_open_days": (now - oldest).days if oldest is not None else None,
        "window_days": WINDOW_DAYS,
        "explained_in_window": int(decided.get(RevenueDifferenceStatus.EXPLAINED, 0)),
        "confirmed_in_window": int(decided.get(RevenueDifferenceStatus.CONFIRMED, 0)),
        "cleared_in_window": int(decided.get(RevenueDifferenceStatus.CLEARED, 0)),
        "items": items,
    }
