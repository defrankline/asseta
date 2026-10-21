from datetime import date

from asseta.modules.platform_billing.entitlement_rules import PolicyTerms, evaluate
from asseta.modules.platform_billing.enums import SubscriptionStatus as S
from asseta.modules.tenancy.models import TenantAccessState as A

POLICY = PolicyTerms(
    grace_days=7,
    suspend_after_days=30,
    past_due_access=A.FULL,
    suspended_access=A.READ_ONLY,
    cancelled_access=A.READ_ONLY,
)
AS_OF = date(2026, 12, 31)


def test_no_overdue_is_active_full() -> None:
    d = evaluate(S.PAST_DUE, False, None, AS_OF, POLICY)
    assert (d.status, d.access) == (S.ACTIVE, A.FULL)


def test_within_grace_stays_active() -> None:
    assert evaluate(S.ACTIVE, False, date(2026, 12, 24), AS_OF, POLICY).status is S.ACTIVE


def test_past_grace_is_past_due_then_suspended_read_only() -> None:
    assert evaluate(S.ACTIVE, False, date(2026, 12, 23), AS_OF, POLICY).status is S.PAST_DUE
    d = evaluate(S.ACTIVE, False, date(2026, 11, 30), AS_OF, POLICY)
    assert (d.status, d.access) == (S.SUSPENDED, A.READ_ONLY)


def test_manual_suspension_persists_after_payment() -> None:
    assert evaluate(S.SUSPENDED, True, None, AS_OF, POLICY).status is S.SUSPENDED


def test_terminal_and_onboarding_states() -> None:
    assert evaluate(S.CANCELLED, False, None, AS_OF, POLICY).access is A.READ_ONLY
    assert evaluate(S.DRAFT, False, None, AS_OF, POLICY).access is A.FULL
