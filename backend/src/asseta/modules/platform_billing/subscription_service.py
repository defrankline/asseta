"""Subscription lifecycle, negotiated rate versions and entitlement evaluation."""

import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import utcnow
from asseta.core.errors import BusinessRuleViolation, Conflict
from asseta.core.outbox import OutboxWriter
from asseta.modules.platform_billing import entitlement_rules
from asseta.modules.platform_billing.dto import (
    EntitlementDto,
    NewRateVersionIn,
    RateVersionDto,
    SubscriptionDto,
    TransitionIn,
)
from asseta.modules.platform_billing.enums import (
    ALLOWED_TRANSITIONS,
    BILLABLE_STATUSES,
    AgreementStatus,
    SubscriptionStatus,
)
from asseta.modules.platform_billing.mappers import period_for, rate_dto
from asseta.modules.platform_billing.models_commercial import (
    EntitlementEvent,
    SubscriptionRateVersion,
    SubscriptionStatusEvent,
    TenantSubscription,
)
from asseta.modules.platform_billing.repository import BillingRepository
from asseta.modules.tenancy.models import Tenant, TenantStatus, VerificationStatus

TOPIC = "asseta.platform.subscription"


class SubscriptionService:
    def __init__(self, session: Session, actor: AuditActor):
        self._s = session
        self._repo = BillingRepository(session)
        self._actor = actor
        self._audit = AuditService(session)
        self._outbox = OutboxWriter(session)

    def get(self, sub: TenantSubscription, today: date) -> SubscriptionDto:
        agreement = self._repo.agreement(sub.agreement_id)
        rate = None
        period = None
        on = max(today, sub.billing_start_date)
        try:
            rate = self._repo.rate_effective(sub.agreement_id, on)
        except BusinessRuleViolation:
            rate = None
        if rate is not None and today >= sub.billing_start_date:
            period = period_for(sub, rate, today)
        enrolled = self._repo.count_active(sub.id, today)
        minimum = rate.minimum_billable_assets if rate else 1
        return SubscriptionDto(
            id=sub.id,
            tenant_id=sub.tenant_id,
            agreement_id=sub.agreement_id,
            agreement_number=agreement.agreement_number,
            status=sub.status,
            start_date=sub.start_date,
            billing_start_date=sub.billing_start_date,
            billing_anchor_day=sub.billing_anchor_day,
            cancellation_effective_date=sub.cancellation_effective_date,
            manually_suspended=sub.manually_suspended,
            payment_terms_days=agreement.payment_terms_days,
            current_rate=rate_dto(rate) if rate else None,
            current_period_start=period.start if period else None,
            current_period_end=period.end if period else None,
            enrolled_assets=enrolled,
            billable_assets=max(enrolled, minimum) if sub.status in BILLABLE_STATUSES else 0,
        )

    def add_rate_version(self, sub: TenantSubscription, body: NewRateVersionIn, today: date) -> RateVersionDto:
        """Renegotiation never rewrites history: a new immutable version takes effect from a future period
        boundary or today; issued invoices keep the version they were computed with."""
        if sub.status in (SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED):
            raise BusinessRuleViolation("Cannot reprice a closed subscription", code="SUBSCRIPTION_CLOSED")
        self._repo.currency(body.currency)
        versions = self._repo.rate_versions(sub.agreement_id)
        if versions and body.effective_from <= versions[-1].effective_from:
            raise Conflict("effective_from must be after the latest rate version", code="RATE_NOT_LATEST")
        if sub.activated_at is not None and body.effective_from < today:
            raise BusinessRuleViolation("Rate changes cannot be backdated", code="RATE_BACKDATED")
        if versions and body.cadence != versions[-1].cadence and sub.status in BILLABLE_STATUSES:
            raise BusinessRuleViolation(
                "Changing cadence of an active subscription requires a new subscription",
                code="CADENCE_CHANGE_UNSUPPORTED",
            )
        rate = SubscriptionRateVersion(
            id=uuid.uuid4(),
            agreement_id=sub.agreement_id,
            tenant_id=sub.tenant_id,
            version=(versions[-1].version + 1) if versions else 1,
            created_by=self._actor.user_id,
            **body.model_dump(),
        )
        self._s.add(rate)
        self._s.flush()
        dto = rate_dto(rate)
        self._audit.record(
            actor=self._actor,
            action="platform.rate_version.created",
            entity_type="subscription",
            entity_id=sub.id,
            tenant_id=sub.tenant_id,
            after=dto.model_dump(mode="json"),
            reason=body.reason,
        )
        self._outbox.emit(
            topic=TOPIC,
            event_type="RateVersionCreated",
            key=str(sub.tenant_id),
            payload=dto.model_dump(mode="json"),
            tenant_id=sub.tenant_id,
        )
        return dto

    def _set_status(self, sub: TenantSubscription, to: SubscriptionStatus, effective: date, reason: str) -> None:
        before = sub.status
        if to not in ALLOWED_TRANSITIONS[before]:
            raise BusinessRuleViolation(
                f"Transition {before.value} -> {to.value} is not allowed", code="INVALID_TRANSITION"
            )
        sub.status = to
        self._s.add(
            SubscriptionStatusEvent(
                id=uuid.uuid4(),
                subscription_id=sub.id,
                tenant_id=sub.tenant_id,
                from_status=before.value,
                to_status=to.value,
                effective_date=effective,
                reason=reason,
                actor_user_id=self._actor.user_id,
            )
        )
        self._audit.record(
            actor=self._actor,
            action="platform.subscription.status_changed",
            entity_type="subscription",
            entity_id=sub.id,
            tenant_id=sub.tenant_id,
            before={"status": before.value},
            after={"status": to.value},
            reason=reason,
        )
        self._outbox.emit(
            topic=TOPIC,
            event_type="SubscriptionStatusChanged",
            key=str(sub.tenant_id),
            payload={
                "subscription_id": str(sub.id),
                "from": before.value,
                "to": to.value,
                "effective_date": effective.isoformat(),
            },
            tenant_id=sub.tenant_id,
        )

    def _close(self, sub: TenantSubscription) -> None:
        self._repo.agreement(sub.agreement_id).status = AgreementStatus.TERMINATED
        tenant = self._s.get(Tenant, sub.tenant_id)
        assert tenant is not None
        tenant.status = TenantStatus.CLOSED

    def transition(self, sub: TenantSubscription, body: TransitionIn, today: date) -> EntitlementDto:
        tenant = self._s.get(Tenant, sub.tenant_id)
        assert tenant is not None
        agreement = self._repo.agreement(sub.agreement_id)
        to = body.to_status
        if to is SubscriptionStatus.ACTIVE and sub.status is SubscriptionStatus.PENDING_ACTIVATION:
            if tenant.verification_status is not VerificationStatus.VERIFIED:
                raise BusinessRuleViolation(
                    "Tenant company record must be verified before activation", code="TENANT_NOT_VERIFIED"
                )
            if not self._repo.rate_versions(sub.agreement_id):
                raise BusinessRuleViolation("A negotiated rate is required", code="NO_RATE")
            if sub.billing_start_date < today:
                sub.billing_start_date = today  # never bill retroactively for pre-activation time
                sub.billing_anchor_day = today.day
            sub.activated_at = utcnow()
            agreement.status = AgreementStatus.ACTIVE
            tenant.status = TenantStatus.ACTIVE
        elif to is SubscriptionStatus.SUSPENDED:
            sub.manually_suspended = True
        elif to is SubscriptionStatus.ACTIVE and sub.status is SubscriptionStatus.SUSPENDED:
            sub.manually_suspended = False
        elif to is SubscriptionStatus.CANCELLED:
            if body.effective_date < today:
                raise BusinessRuleViolation("Cancellation cannot be backdated", code="CANCEL_BACKDATED")
            sub.cancellation_effective_date = body.effective_date
            if body.effective_date > today:  # scheduled: stays billable until the date, then auto-cancels
                self._audit.record(
                    actor=self._actor,
                    action="platform.subscription.cancellation_scheduled",
                    entity_type="subscription",
                    entity_id=sub.id,
                    tenant_id=sub.tenant_id,
                    after={"cancellation_effective_date": body.effective_date.isoformat()},
                    reason=body.reason,
                )
                return self.evaluate_entitlement(sub, today)
            self._close(sub)
        elif to in (SubscriptionStatus.PAST_DUE, SubscriptionStatus.EXPIRED):
            raise BusinessRuleViolation(
                f"{to.value} is set automatically by entitlement evaluation", code="AUTOMATIC_STATUS"
            )
        self._set_status(sub, to, body.effective_date, body.reason)
        return self.evaluate_entitlement(sub, today)

    def evaluate_entitlement(self, sub: TenantSubscription, as_of: date) -> EntitlementDto:
        tenant = self._s.get(Tenant, sub.tenant_id, with_for_update=True)
        assert tenant is not None
        policy = self._repo.entitlement_policy(sub.tenant_id, as_of)
        terms = entitlement_rules.PolicyTerms(
            policy.grace_days,
            policy.suspend_after_days,
            policy.past_due_access,
            policy.suspended_access,
            policy.cancelled_access,
        )
        if (
            sub.status in BILLABLE_STATUSES
            and sub.cancellation_effective_date
            and as_of >= sub.cancellation_effective_date
        ):
            self._set_status(sub, SubscriptionStatus.CANCELLED, as_of, "Cancellation effective date reached")
            self._close(sub)
        overdue = self._repo.oldest_overdue_due_date(sub.tenant_id, as_of)
        decision = entitlement_rules.evaluate(sub.status, sub.manually_suspended, overdue, as_of, terms)
        if decision.status != sub.status and sub.status in BILLABLE_STATUSES:
            self._set_status(sub, decision.status, as_of, f"Automatic: {decision.reason}")
        changed = tenant.access_state != decision.access
        if changed:
            self._s.add(
                EntitlementEvent(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    subscription_id=sub.id,
                    from_access=tenant.access_state.value,
                    to_access=decision.access.value,
                    subscription_status=sub.status.value,
                    policy_id=policy.id,
                    policy_version=policy.version,
                    reason=decision.reason,
                )
            )
            self._audit.record(
                actor=self._actor,
                action="platform.entitlement.changed",
                entity_type="tenant",
                entity_id=tenant.id,
                tenant_id=tenant.id,
                before={"access_state": tenant.access_state.value},
                after={"access_state": decision.access.value},
                reason=decision.reason,
                policy_version=str(policy.version),
            )
            tenant.access_state = decision.access
            tenant.access_state_changed_at = utcnow()
        # The reason explains the current state even when the access level is unchanged (TRIAL -> ACTIVE stays FULL).
        if tenant.access_state_reason != decision.reason[:200]:
            tenant.access_state_reason = decision.reason[:200]
        return EntitlementDto(
            tenant_id=tenant.id,
            subscription_status=sub.status,
            access_state=tenant.access_state.value,
            reason=decision.reason,
            policy_version=policy.version,
            changed=changed,
        )


def default_billing_start(start: date, trial_days: int) -> date:
    return start + timedelta(days=trial_days)
