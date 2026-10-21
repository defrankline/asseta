"""Billable-asset enrollment lifecycle with explicit preview of mid-cycle financial effect.

Rules (documented default policy; terms come from the effective rate version):
* A machine counts once (open-enrollment unique index); tracker swaps do not touch enrollments.
* Recurring invoices bill machines active at period start. A change at date d inside the current period
  creates a pending proration charge/credit when d > period start, or when d == period start and that
  period's invoice is already issued. Issued invoices are never rewritten.
* Changes may not be backdated before the current period; corrections go through credit adjustments.
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.modules.fleet.models import Machine, MachineStatus
from asseta.modules.platform_billing.calendar import Period
from asseta.modules.platform_billing.dto import ChargePreviewDto, EnrollmentDto, EnrollmentResultDto
from asseta.modules.platform_billing.enums import (
    EnrollmentEndReason,
    InvoiceLineType,
    PendingChargeStatus,
    SubscriptionStatus,
)
from asseta.modules.platform_billing.mappers import period_for, rate_terms
from asseta.modules.platform_billing.models_commercial import SubscriptionRateVersion, TenantSubscription
from asseta.modules.platform_billing.models_ledger import SubscriptionAssetEnrollment, SubscriptionPendingCharge
from asseta.modules.platform_billing.pricing import ProrationResult, prorate_add, prorate_remove
from asseta.modules.platform_billing.repository import BillingRepository

TOPIC = "asseta.platform.enrollment"
_CLOSED = (SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED)


@dataclass(frozen=True)
class _Effect:
    period: Period
    rate: SubscriptionRateVersion
    result: ProrationResult


class EnrollmentService:
    def __init__(self, session: Session, actor: AuditActor):
        self._s = session
        self._repo = BillingRepository(session)
        self._actor = actor
        self._audit = AuditService(session)
        self._outbox = OutboxWriter(session)

    # --- validation -----------------------------------------------------------------------------------
    def _change_period(
        self, sub: TenantSubscription, d: date, today: date
    ) -> tuple[Period, SubscriptionRateVersion] | None:
        if sub.status in _CLOSED:
            raise BusinessRuleViolation("Subscription is closed", code="SUBSCRIPTION_CLOSED")
        if d < sub.start_date:
            raise BusinessRuleViolation("Date precedes subscription start", code="DATE_BEFORE_SUBSCRIPTION")
        not_billing = (
            sub.status in (SubscriptionStatus.DRAFT, SubscriptionStatus.PENDING_ACTIVATION)
            or today < sub.billing_start_date
        )
        if not_billing:
            if d > today:
                raise BusinessRuleViolation("Enrollment changes cannot be future-dated", code="DATE_IN_FUTURE")
            return None  # before billing starts: counted at first period start, no proration
        rate = self._repo.rate_effective(sub.agreement_id, d)
        current = period_for(sub, rate, today)
        if not current.contains(d):
            raise BusinessRuleViolation(
                f"Date must fall in the current billing period {current.start}..{current.end}",
                code="DATE_OUTSIDE_CURRENT_PERIOD",
            )
        return current, rate

    def _needs_charge(self, sub: TenantSubscription, period: Period, d: date) -> bool:
        return d > period.start or self._repo.invoice_for_period(sub.id, period.start) is not None

    def _preview(self, effect: _Effect | None) -> ChargePreviewDto | None:
        if effect is None:
            return None
        r = effect.result
        return ChargePreviewDto(
            line_type=r.line_type,
            service_from=effect.period.end - timedelta(days=r.days),
            service_to=effect.period.end,
            days=r.days,
            period_days=effect.period.days,
            amount=r.amount,
            currency=effect.rate.currency,
            explanation=r.explanation,
        )

    # --- add ------------------------------------------------------------------------------------------
    def _add_effect(self, sub: TenantSubscription, d: date, today: date) -> _Effect | None:
        pr = self._change_period(sub, d, today)
        if pr is None:
            return None
        period, rate = pr
        if not self._needs_charge(sub, period, d):
            return None
        terms = rate_terms(rate, self._repo.currency(rate.currency))
        return _Effect(period, rate, prorate_add(terms, period, d, self._repo.count_active(sub.id, d)))

    def _machine(self, machine_id: uuid.UUID) -> Machine:
        machine = self._s.execute(select(Machine).where(Machine.id == machine_id)).scalar_one_or_none()
        if machine is None:  # RLS hides other tenants' machines -> indistinguishable from missing
            raise NotFound("Machine not found")
        if machine.status is MachineStatus.DISPOSED:
            raise BusinessRuleViolation("Disposed machines cannot be enrolled", code="MACHINE_DISPOSED")
        return machine

    def preview_add(
        self, sub: TenantSubscription, machine_id: uuid.UUID, d: date, today: date
    ) -> ChargePreviewDto | None:
        self._machine(machine_id)
        return self._preview(self._add_effect(sub, d, today))

    def enroll(self, sub: TenantSubscription, machine_id: uuid.UUID, d: date, today: date) -> EnrollmentResultDto:
        machine = self._machine(machine_id)
        open_enrollment = self._repo.open_enrollment_for_machine(machine_id)
        if open_enrollment is not None:
            if open_enrollment.subscription_id == sub.id and open_enrollment.effective_from == d:
                return EnrollmentResultDto(enrollment=EnrollmentDto.model_validate(open_enrollment), charge=None)
            raise Conflict("Machine is already enrolled as a billable asset", code="ALREADY_ENROLLED")
        effect = self._add_effect(sub, d, today)
        enrollment = SubscriptionAssetEnrollment(
            id=uuid.uuid4(),
            tenant_id=sub.tenant_id,
            subscription_id=sub.id,
            machine_id=machine.id,
            asset_label=machine.asset_code,
            effective_from=d,
            created_by=self._actor.user_id,
        )
        self._s.add(enrollment)
        self._s.flush()
        self._persist_charge(sub, enrollment, effect)
        dto = EnrollmentDto.model_validate(enrollment)
        self._audit.record(
            actor=self._actor,
            action="billing.asset.enrolled",
            entity_type="enrollment",
            entity_id=enrollment.id,
            tenant_id=sub.tenant_id,
            after=dto.model_dump(mode="json"),
        )
        self._outbox.emit(
            topic=TOPIC,
            event_type="BillableAssetEnrolled",
            key=str(sub.tenant_id),
            payload=dto.model_dump(mode="json"),
            tenant_id=sub.tenant_id,
        )
        return EnrollmentResultDto(enrollment=dto, charge=self._preview(effect))

    # --- remove ---------------------------------------------------------------------------------------
    def _remove_effect(
        self, sub: TenantSubscription, e: SubscriptionAssetEnrollment, d: date, today: date
    ) -> _Effect | None:
        if d < e.effective_from:
            raise BusinessRuleViolation("End date precedes enrollment start", code="END_BEFORE_START")
        pr = self._change_period(sub, d, today)
        if pr is None:
            return None
        period, rate = pr
        terms = rate_terms(rate, self._repo.currency(rate.currency))
        billed_at_start = e.effective_from <= period.start
        if billed_at_start and not self._needs_charge(sub, period, d):
            return None
        if not billed_at_start:
            add_charge = self._s.execute(
                select(SubscriptionPendingCharge).where(
                    SubscriptionPendingCharge.enrollment_id == e.id,
                    SubscriptionPendingCharge.line_type == InvoiceLineType.PRORATION_CHARGE,
                )
            ).scalar_one_or_none()
            if add_charge is None or add_charge.amount == 0:
                return None  # never charged for this period -> nothing to credit
        active_after = self._repo.count_active(sub.id, d, exclude=e.id)
        return _Effect(period, rate, prorate_remove(terms, period, d, active_after))

    def preview_end(
        self, sub: TenantSubscription, enrollment_id: uuid.UUID, d: date, today: date
    ) -> ChargePreviewDto | None:
        e = self._repo.enrollment(enrollment_id)
        return self._preview(self._remove_effect(sub, e, d, today))

    def end(
        self, sub: TenantSubscription, enrollment_id: uuid.UUID, d: date, reason: EnrollmentEndReason, today: date
    ) -> EnrollmentResultDto:
        e = self._repo.enrollment(enrollment_id)
        if e.subscription_id != sub.id:
            raise NotFound("Enrollment not found")
        if e.effective_to is not None:
            if e.effective_to == d:
                return EnrollmentResultDto(enrollment=EnrollmentDto.model_validate(e), charge=None)
            raise Conflict("Enrollment already ended", code="ENROLLMENT_ENDED")
        effect = self._remove_effect(sub, e, d, today)
        before = EnrollmentDto.model_validate(e).model_dump(mode="json")
        e.effective_to, e.end_reason, e.ended_by = d, reason, self._actor.user_id
        self._s.flush()
        self._persist_charge(sub, e, effect)
        dto = EnrollmentDto.model_validate(e)
        self._audit.record(
            actor=self._actor,
            action="billing.asset.unenrolled",
            entity_type="enrollment",
            entity_id=e.id,
            tenant_id=sub.tenant_id,
            before=before,
            after=dto.model_dump(mode="json"),
            reason=reason.value,
        )
        self._outbox.emit(
            topic=TOPIC,
            event_type="BillableAssetUnenrolled",
            key=str(sub.tenant_id),
            payload=dto.model_dump(mode="json"),
            tenant_id=sub.tenant_id,
        )
        return EnrollmentResultDto(enrollment=dto, charge=self._preview(effect))

    def _persist_charge(self, sub: TenantSubscription, e: SubscriptionAssetEnrollment, effect: _Effect | None) -> None:
        if effect is None:
            return
        r = effect.result
        preview = self._preview(effect)
        assert preview is not None and preview.service_from is not None
        self._s.add(
            SubscriptionPendingCharge(
                id=uuid.uuid4(),
                tenant_id=sub.tenant_id,
                subscription_id=sub.id,
                enrollment_id=e.id,
                rate_version_id=effect.rate.id,
                line_type=r.line_type,
                service_from=preview.service_from,
                service_to=effect.period.end,
                days=r.days,
                period_days=effect.period.days,
                computed_amount=r.amount,
                amount=r.amount,
                explanation=f"{e.asset_label}: {r.explanation}",
                status=PendingChargeStatus.PENDING if r.amount != 0 else PendingChargeStatus.WAIVED,
            )
        )
