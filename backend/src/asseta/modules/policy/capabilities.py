"""Tenant capabilities: features a tenant's effective policy can switch off as a whole. The single source of truth
for "is this capability on for this tenant now" — navigation (menu catalog `capability`), endpoint and sync-operation
refusals, the sync capability announcement, dashboard tiles and scheduled sweeps read it from here, never from a
second copy of the rule.

Off keeps the behaviour that existed before the capability (a safe platform default turns each one on)."""

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from asseta.core.errors import BusinessRuleViolation
from asseta.modules.policy.service import PolicyService

Check = Callable[[PolicyService, uuid.UUID, datetime], bool]

CUSTOMER_HOURS = "CUSTOMER_HOURS"
ENGINE_HOURS = "ENGINE_HOURS"
CASH_CUSTODY = "CASH_CUSTODY"

CAPABILITIES: dict[str, Check] = {
    # Customer prepaid hours (CUSTOMER_HOURS.enabled): purchases, balances, approvals, reason lists.
    CUSTOMER_HOURS: lambda svc, tid, at: svc.customer_hours(tid, at=at).policy.enabled,
    # Engine-hour accountability (ENGINE_HOURS.enabled): reconciliation, explanations, baselines, corrections, daily
    # readings, reason lists, and the START gate / daily-report / unexplained-hours sweeps.
    ENGINE_HOURS: lambda svc, tid, at: svc.engine_hours(tid, at=at).policy.enabled,
    # Cash custody chain controls (CASH_CUSTODY.enabled): transfers, acknowledgements, variances and write-offs,
    # retentions, custody adjustments, cash reasons, the remittance cut-off, partial-remittance flag and recording
    # for others. The cash basics (collections, floats, remittances, reconciliation) are not part of it.
    CASH_CUSTODY: lambda svc, tid, at: svc.cash_custody(tid, at=at).policy.enabled,
}

# How a request needing a switched-off capability is refused: 422 BUSINESS_RULE_VIOLATION envelope with this code
# (CUSTOMER_HOURS keeps the code its services already used). Offline sync operations get the same code as CONFLICT.
REFUSALS: dict[str, tuple[str, str]] = {
    CUSTOMER_HOURS: ("HOURS_DISABLED", "Customer hours are switched off for this tenant"),
    ENGINE_HOURS: ("ENGINE_HOURS_DISABLED", "Engine-hour controls are switched off for this tenant"),
    CASH_CUSTODY: ("CASH_CUSTODY_DISABLED", "Cash custody controls are switched off for this tenant"),
}


def capability_on(session: Session, tenant_id: uuid.UUID, code: str, at: datetime) -> bool:
    """Whether one capability is on for the tenant at `at` (read in the tenant's RLS scope). A policy that is not
    configured counts as on (the platform default)."""
    try:
        return CAPABILITIES[code](PolicyService(session), tenant_id, at)
    except BusinessRuleViolation:
        return True


def require_capability(session: Session, tenant_id: uuid.UUID, code: str, at: datetime) -> None:
    """Refuse (422, REFUSALS code) when the tenant switched the capability off."""
    if not capability_on(session, tenant_id, code, at):
        refusal, message = REFUSALS[code]
        raise BusinessRuleViolation(message, code=refusal)


def disabled_capabilities(session: Session, tenant_id: uuid.UUID, at: datetime) -> frozenset[str]:
    """Capabilities switched off by the tenant's effective policy at `at` (read in the tenant's RLS scope)."""
    return frozenset(code for code in CAPABILITIES if not capability_on(session, tenant_id, code, at))
