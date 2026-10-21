"""Deterministic entitlement evaluation: subscription status + overdue state + versioned policy -> access."""

from dataclasses import dataclass
from datetime import date

from asseta.modules.platform_billing.enums import SubscriptionStatus
from asseta.modules.tenancy.models import TenantAccessState


@dataclass(frozen=True)
class PolicyTerms:
    grace_days: int
    suspend_after_days: int
    past_due_access: TenantAccessState
    suspended_access: TenantAccessState
    cancelled_access: TenantAccessState


@dataclass(frozen=True)
class EntitlementDecision:
    status: SubscriptionStatus
    access: TenantAccessState
    reason: str


def evaluate(
    status: SubscriptionStatus,
    manually_suspended: bool,
    oldest_overdue_due_date: date | None,
    as_of: date,
    policy: PolicyTerms,
) -> EntitlementDecision:
    if status in (SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED):
        return EntitlementDecision(status, policy.cancelled_access, f"Subscription {status.value}")
    if status in (SubscriptionStatus.DRAFT, SubscriptionStatus.PENDING_ACTIVATION):
        return EntitlementDecision(status, TenantAccessState.FULL, "Onboarding: setup access")
    if manually_suspended:
        return EntitlementDecision(SubscriptionStatus.SUSPENDED, policy.suspended_access, "Suspended by platform")
    overdue_days = (as_of - oldest_overdue_due_date).days if oldest_overdue_due_date else 0
    if overdue_days > policy.suspend_after_days:
        return EntitlementDecision(
            SubscriptionStatus.SUSPENDED,
            policy.suspended_access,
            f"Invoice overdue {overdue_days} days (> {policy.suspend_after_days})",
        )
    if overdue_days > policy.grace_days:
        return EntitlementDecision(
            SubscriptionStatus.PAST_DUE,
            policy.past_due_access,
            f"Invoice overdue {overdue_days} days (> grace {policy.grace_days})",
        )
    reason = f"Within grace ({overdue_days} days overdue)" if overdue_days > 0 else "No overdue balance"
    return EntitlementDecision(SubscriptionStatus.ACTIVE, TenantAccessState.FULL, reason)
