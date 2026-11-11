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
from asseta.modules.policy.managed_switch import has_open_mandate
from asseta.modules.policy.service import PolicyService

Check = Callable[[PolicyService, uuid.UUID, datetime], bool]

CUSTOMER_HOURS = "CUSTOMER_HOURS"
ENGINE_HOURS = "ENGINE_HOURS"
CASH_CUSTODY = "CASH_CUSTODY"
REVENUE_RECONCILIATION = "REVENUE_RECONCILIATION"
SCORECARD = "SCORECARD"
UNBILLED_WORK = "UNBILLED_WORK"
IDLE_MACHINES = "IDLE_MACHINES"
SITE_CHECKIN = "SITE_CHECKIN"
INSIGHTS = "INSIGHTS"
INVESTIGATIONS = "INVESTIGATIONS"
TRACKING = "TRACKING"
DEPOSIT_ACCOUNTS = "DEPOSIT_ACCOUNTS"
MANAGED_SERVICE = "MANAGED_SERVICE"
PETTY_CASH = "PETTY_CASH"

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
    # Revenue reconciliation (REVENUE_RECONCILIATION.enabled, DEC-031 Phase 1; platform default OFF): the
    # revenue-hour basis (non-revenue bucket), the daily machine sheet, revenue differences, their reasons and sweep.
    REVENUE_RECONCILIATION: lambda svc, tid, at: svc.revenue_reconciliation(tid, at=at).policy.enabled,
    # DEC-031 Phase 5 oversight (OVERSIGHT policy; platform default OFF): the per-person scorecard and its
    # repeat-pattern signals (scorecard_enabled), unbilled work (unbilled_after_days set), idle machines
    # (idle_after_days set) and supervisors' site check-ins (site_checkin_required).
    SCORECARD: lambda svc, tid, at: svc.oversight(tid, at=at).policy.scorecard_enabled,
    UNBILLED_WORK: lambda svc, tid, at: svc.oversight(tid, at=at).policy.unbilled_after_days is not None,
    IDLE_MACHINES: lambda svc, tid, at: svc.oversight(tid, at=at).policy.idle_after_days is not None,
    SITE_CHECKIN: lambda svc, tid, at: svc.oversight(tid, at=at).policy.site_checkin_required,
    # DEC-032 optional modules (platform default ON; a company turns off what it does not use). Each hides its menus,
    # refuses its endpoints and stops its background work; recorded business data is never touched.
    # Insights page: machine insights, cash trend, manual-override audit and model observations.
    INSIGHTS: lambda svc, tid, at: svc.oversight(tid, at=at).policy.insights_enabled,
    # Investigation cases: no case is opened or joined (variances, differences and signals are still recorded).
    INVESTIGATIONS: lambda svc, tid, at: svc.oversight(tid, at=at).policy.investigations_enabled,
    # Trackers, geofences and tracking alerts. Machines, job sites, the fleet map and billing enrollment are not part
    # of it; messages from this tenant's trackers are ignored while it is off (TRACKING.enabled; tenant level only).
    TRACKING: lambda svc, tid, at: svc.tracking(tid, at=at).policy.enabled,
    # Company deposit accounts (CASH_CUSTODY.deposit_accounts_enabled); off, remittance_account_required reads off.
    DEPOSIT_ACCOUNTS: lambda svc, tid, at: svc.cash_custody(tid, at=at).policy.deposit_accounts_enabled,
    # Only the tenant's own Managed service page: mandates stay in force and platform governance is unaffected. Never
    # off while a mandate is open, however the switch came to be off (a future-dated version, a mandate granted later).
    MANAGED_SERVICE: lambda svc, tid, at: (
        svc.oversight(tid, at=at).policy.managed_service_enabled or has_open_mandate(svc.session, tid, at)
    ),
    # DEC-033 petty cash funds (PETTY_CASH.enabled; platform default OFF): funds, fundings and top-ups, returns,
    # counts, holder changes, fund adjustments, advances, fund expenses and their variances, menus and sweeps.
    PETTY_CASH: lambda svc, tid, at: svc.petty_cash(tid, at=at).policy.enabled,
}

# Capabilities whose safe platform default is OFF (a tenant opts in): an unconfigured policy counts as off for them.
OFF_BY_DEFAULT = frozenset({REVENUE_RECONCILIATION, SCORECARD, UNBILLED_WORK, IDLE_MACHINES, SITE_CHECKIN, PETTY_CASH})

# How a request needing a switched-off capability is refused: 422 BUSINESS_RULE_VIOLATION envelope with this code
# (CUSTOMER_HOURS keeps the code its services already used). Offline sync operations get the same code as CONFLICT.
REFUSALS: dict[str, tuple[str, str]] = {
    CUSTOMER_HOURS: ("HOURS_DISABLED", "Customer hours are switched off for this tenant"),
    ENGINE_HOURS: ("ENGINE_HOURS_DISABLED", "Engine-hour controls are switched off for this tenant"),
    CASH_CUSTODY: ("CASH_CUSTODY_DISABLED", "Cash custody controls are switched off for this tenant"),
    REVENUE_RECONCILIATION: (
        "REVENUE_RECONCILIATION_DISABLED",
        "Revenue reconciliation is switched off for this tenant",
    ),
    SCORECARD: ("SCORECARD_DISABLED", "The people scorecard is switched off for this tenant"),
    UNBILLED_WORK: ("UNBILLED_WORK_DISABLED", "The unbilled-work check is switched off for this tenant"),
    IDLE_MACHINES: ("IDLE_MACHINES_DISABLED", "The idle-machine check is switched off for this tenant"),
    SITE_CHECKIN: ("SITE_CHECKIN_DISABLED", "Site check-ins are switched off for this tenant"),
    INSIGHTS: ("INSIGHTS_DISABLED", "Insights are switched off for this tenant"),
    INVESTIGATIONS: ("INVESTIGATIONS_DISABLED", "Investigations are switched off for this tenant"),
    TRACKING: ("TRACKING_DISABLED", "Tracking is switched off for this tenant"),
    DEPOSIT_ACCOUNTS: ("DEPOSIT_ACCOUNTS_DISABLED", "Deposit accounts are switched off for this tenant"),
    MANAGED_SERVICE: ("MANAGED_SERVICE_DISABLED", "The managed service page is switched off for this tenant"),
    PETTY_CASH: ("PETTY_CASH_DISABLED", "Petty cash funds are switched off for this tenant"),
}


def capability_on(session: Session, tenant_id: uuid.UUID, code: str, at: datetime) -> bool:
    """Whether one capability is on for the tenant at `at` (read in the tenant's RLS scope). A policy that is not
    configured counts as its platform default (on, except the OFF_BY_DEFAULT ones)."""
    try:
        return CAPABILITIES[code](PolicyService(session), tenant_id, at)
    except BusinessRuleViolation:
        return code not in OFF_BY_DEFAULT


def require_capability(session: Session, tenant_id: uuid.UUID, code: str, at: datetime) -> None:
    """Refuse (422, REFUSALS code) when the tenant switched the capability off."""
    if not capability_on(session, tenant_id, code, at):
        refusal, message = REFUSALS[code]
        raise BusinessRuleViolation(message, code=refusal)


def disabled_capabilities(session: Session, tenant_id: uuid.UUID, at: datetime) -> frozenset[str]:
    """Capabilities switched off by the tenant's effective policy at `at` (read in the tenant's RLS scope)."""
    return frozenset(code for code in CAPABILITIES if not capability_on(session, tenant_id, code, at))
