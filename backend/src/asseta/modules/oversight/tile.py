"""Accountability dashboard tiles for DEC-031 M2: unbilled work and idle machines (links to their lists and the
records). Hidden while the tenant has the check off (capabilities UNBILLED_WORK / IDLE_MACHINES)."""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from asseta.modules.identity.principal import RequestContext
from asseta.modules.oversight.idle import idle_machines
from asseta.modules.oversight.unbilled import unbilled_jobs
from asseta.modules.policy.service import PolicyService

ITEMS = 20


def unbilled_work_tile(s: Session, ctx: RequestContext, now: datetime) -> dict[str, Any]:
    assert ctx.tenant_id is not None
    rows = unbilled_jobs(s, ctx.tenant_id, now)
    amounts: dict[str, list[Decimal]] = defaultdict(list)
    for r in rows:
        if r.total is not None:
            amounts[r.currency].append(r.total)
    return {
        "count": len(rows),
        "after_days": PolicyService(s).oversight(ctx.tenant_id, at=now).policy.unbilled_after_days,
        "amounts": [
            {"currency": c, "count": len(v), "amount": str(sum(v, Decimal(0)))} for c, v in sorted(amounts.items())
        ],
        "oldest_days": max((r.days_unbilled for r in rows), default=None),
        "items": [
            {
                "job_id": str(r.job_id),
                "machine_id": str(r.machine_id),
                "customer_id": str(r.customer_id),
                "completed_at": r.completed_at.isoformat(),
                "days_unbilled": r.days_unbilled,
                "currency": r.currency,
                "total": str(r.total) if r.total is not None else None,
            }
            for r in rows[:ITEMS]
        ],
    }


def idle_machines_tile(s: Session, ctx: RequestContext, now: datetime) -> dict[str, Any]:
    assert ctx.tenant_id is not None
    rows = idle_machines(s, ctx.tenant_id, now)
    return {
        "count": len(rows),
        "after_days": PolicyService(s).oversight(ctx.tenant_id, at=now).policy.idle_after_days,
        "longest_idle_days": max((r.idle_days for r in rows), default=None),
        "items": [
            {
                "machine_id": str(r.machine_id),
                "idle_since": r.idle_since.isoformat(),
                "idle_days": r.idle_days,
                "planned_job_id": str(r.planned_job_id) if r.planned_job_id else None,
            }
            for r in rows[:ITEMS]
        ],
    }
