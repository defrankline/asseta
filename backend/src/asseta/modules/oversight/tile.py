"""Accountability dashboard tile for DEC-031 M2: idle machines (links to their list and the records). Hidden while
the tenant has the check off (capability IDLE_MACHINES)."""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from asseta.modules.accountability.names import fill_names
from asseta.modules.identity.principal import RequestContext
from asseta.modules.oversight.idle import idle_machines
from asseta.modules.policy.service import PolicyService

ITEMS = 20


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
                "machine_code": r.machine_code,
                "machine_name": r.machine_name,
                "idle_since": r.idle_since.isoformat(),
                "idle_days": r.idle_days,
                "last_machine_report_id": str(r.last_machine_report_id) if r.last_machine_report_id else None,
                "last_machine_report_number": r.last_machine_report_number,
            }
            for r in fill_names(s, rows[:ITEMS])
        ],
    }
