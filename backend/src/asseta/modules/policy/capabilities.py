"""Tenant capabilities: features a tenant's effective policy can switch off as a whole. The single source of truth
for "is this capability on for this tenant now" — navigation (menu catalog `capability`) and anything else that
hides a whole feature read it from here, never from a second copy of the rule.

Off keeps the behaviour that existed before the capability (a safe platform default turns each one on)."""

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from asseta.core.errors import BusinessRuleViolation
from asseta.modules.policy.service import PolicyService

Check = Callable[[PolicyService, uuid.UUID, datetime], bool]

CAPABILITIES: dict[str, Check] = {
    # Customer prepaid hours (CUSTOMER_HOURS.enabled): purchases, balances, approvals, reason lists.
    "CUSTOMER_HOURS": lambda svc, tid, at: svc.customer_hours(tid, at=at).policy.enabled,
}


def disabled_capabilities(session: Session, tenant_id: uuid.UUID, at: datetime) -> frozenset[str]:
    """Capabilities switched off by the tenant's effective policy at `at` (read in the tenant's RLS scope). A policy
    that is not configured counts as on (the platform default)."""
    svc = PolicyService(session)
    off = set()
    for code, check in CAPABILITIES.items():
        try:
            if not check(svc, tenant_id, at):
                off.add(code)
        except BusinessRuleViolation:
            continue
    return frozenset(off)
