"""Customer hours engine: activation (verified money / authorised credit only), Work Execution Allocation on job
completion (FIFO under row locks), overrun handling, the START gate. Called from the hours service, the payment
decision and the jobs lifecycle; every write is a ledger entry plus an audit event."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.errors import BusinessRuleViolation, NotFound
from asseta.core.money import quantize
from asseta.core.outbox import OutboxWriter
from asseta.modules.finance.models import CustomerPayment, SettlementStatus
from asseta.modules.hours.ledger import (
    ZERO,
    LedgerWriter,
    allocated_amounts,
    expiry_of,
    floor_to,
    purchase_totals,
)
from asseta.modules.hours.models import (
    SIGN,
    ActivationSource,
    CreditArrangement,
    HoursLedgerEntry,
    HoursPaymentAllocation,
    HoursPurchase,
    LedgerEntryType,
    ProposalStatus,
    WorkExecutionAllocation,
)
from asseta.modules.jobs.models import Job, RentalContract
from asseta.modules.meter.models import ExceptionStatus, ExceptionType, JobException
from asseta.modules.platform_billing.models_commercial import Currency
from asseta.modules.policy.schemas import ActivationBasis, BillingMode, CustomerHoursPolicy, OverConsumption
from asseta.modules.policy.service import EffectivePolicy, PolicyService

TOPIC = "asseta.hours"
T = LedgerEntryType


def hours_policy(session: Session, tenant_id: uuid.UUID, at: datetime) -> EffectivePolicy[CustomerHoursPolicy]:
    return PolicyService(session).customer_hours(tenant_id, at=at)


def job_customer(session: Session, job: Job) -> uuid.UUID:
    contract = session.get(RentalContract, job.contract_id)
    assert contract is not None
    return contract.customer_id


def available_hours(session: Session, customer_id: uuid.UUID, machine_id: uuid.UUID) -> Decimal:
    """Remaining activated hours of the customer on the machine, over all non-cancelled purchases."""
    rows = session.execute(
        select(HoursLedgerEntry.entry_type, HoursLedgerEntry.hours)
        .join(HoursPurchase, HoursPurchase.id == HoursLedgerEntry.purchase_id)
        .where(
            HoursLedgerEntry.customer_id == customer_id,
            HoursLedgerEntry.machine_id == machine_id,
            HoursPurchase.cancelled_at.is_(None),
        )
    )
    return sum((SIGN[t] * Decimal(h) for t, h in rows), ZERO)


def minor_units(session: Session, currency: str) -> int:
    row = session.get(Currency, currency)
    return row.minor_units if row is not None else 2


class HoursEngine:
    def __init__(self, session: Session, tenant_id: uuid.UUID, actor: AuditActor, now: datetime):
        self._s, self._tid, self._actor, self._now = session, tenant_id, actor, now
        self._audit = AuditService(session)
        self._ledger = LedgerWriter(session, tenant_id, actor.user_id, now)
        self._eff: EffectivePolicy[CustomerHoursPolicy] | None = None

    @property
    def eff(self) -> EffectivePolicy[CustomerHoursPolicy]:
        if self._eff is None:
            self._eff = hours_policy(self._s, self._tid, self._now)
        return self._eff

    @property
    def policy(self) -> CustomerHoursPolicy:
        return self.eff.policy

    def lock_purchase(self, purchase_id: uuid.UUID) -> HoursPurchase:
        row = self._s.execute(
            select(HoursPurchase).where(HoursPurchase.id == purchase_id).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise NotFound("Hours purchase not found")
        return row

    def _record(
        self, action: str, purchase: HoursPurchase, after: dict[str, object], reason: str | None = None
    ) -> None:
        self._audit.record(
            actor=self._actor,
            action=action,
            entity_type="hours_purchase",
            entity_id=purchase.id,
            tenant_id=self._tid,
            after={"purchase_number": purchase.purchase_number, **after},
            reason=reason,
            policy_version=self.eff.version_stamp[:64],
        )

    def _emit(self, event_type: str, purchase: HoursPurchase, payload: dict[str, object]) -> None:
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type=event_type,
            key=str(purchase.customer_id),
            payload={
                "purchase_id": str(purchase.id),
                "purchase_number": purchase.purchase_number,
                "customer_id": str(purchase.customer_id),
                "machine_id": str(purchase.machine_id),
                **payload,
            },
            tenant_id=self._tid,
        )

    # --- activation -----------------------------------------------------------------------------------------
    def activate_from_payments(self, purchase: HoursPurchase, payment_id: uuid.UUID | None = None) -> Decimal:
        """Raise activated hours to what VERIFIED allocated money pays for (never anything else). Credit-activated
        hours count as already active: later payments settle them before activating more."""
        if purchase.cancelled_at is not None or ActivationBasis.VERIFIED_PAYMENT not in self.policy.activation_basis:
            return ZERO
        verified, _ = allocated_amounts(self._s, purchase.id)
        if purchase.amount <= 0:
            target = purchase.hours  # fully discounted by an approved discount: nothing to pay
        elif self.policy.partial_activation:
            target = min(purchase.hours, floor_to(verified / purchase.effective_rate, self.policy.hours_increment))
        else:
            target = purchase.hours if verified >= purchase.amount else ZERO
        totals = purchase_totals(self._s, purchase)
        new = target - totals.net_activated
        if new <= 0:
            return ZERO
        entry = self._ledger.add(
            purchase,
            purchase.machine_id,
            T.ACTIVATED,
            new,
            source=ActivationSource.PAYMENT,
            expires_at=expiry_of(self._now, self.policy.expiry_days),
            payment_id=payment_id,
            reason="Verified payment",
            policy_version=self.eff.version_stamp,
        )
        self._record(
            "hours.activated",
            purchase,
            {"hours": str(new), "source": "PAYMENT", "verified_amount": str(verified), "entry_id": str(entry.id)},
        )
        self._emit("CustomerHoursActivated", purchase, {"hours": str(new), "source": "PAYMENT"})
        self.cover_overruns(purchase.customer_id, purchase.machine_id)
        return new

    def credit_exposure(self, customer_id: uuid.UUID, currency: str) -> Decimal:
        """Activated value not covered by verified money, over the customer's purchases in `currency`."""
        exposure = ZERO
        units = minor_units(self._s, currency)
        for p in self._s.execute(
            select(HoursPurchase).where(HoursPurchase.customer_id == customer_id, HoursPurchase.currency == currency)
        ).scalars():
            totals = purchase_totals(self._s, p)
            value = min(p.amount, quantize(totals.net_activated * p.effective_rate, units))
            verified, _ = allocated_amounts(self._s, p.id)
            exposure += max(ZERO, value - verified)
        return exposure

    def arrangement(self, customer_id: uuid.UUID, currency: str) -> CreditArrangement | None:
        today = self._now.date()
        return self._s.execute(
            select(CreditArrangement)
            .where(
                CreditArrangement.customer_id == customer_id,
                CreditArrangement.currency == currency,
                CreditArrangement.status == ProposalStatus.APPROVED,
                CreditArrangement.effective_from <= today,
                (CreditArrangement.effective_to.is_(None)) | (CreditArrangement.effective_to >= today),
            )
            .order_by(CreditArrangement.effective_from.desc())
            .limit(1)
        ).scalar_one_or_none()

    def activate_on_credit(self, purchase: HoursPurchase, hours: Decimal, reason: str) -> HoursLedgerEntry:
        p = self.policy
        if not p.credit_allowed or ActivationBasis.CREDIT not in p.activation_basis:
            raise BusinessRuleViolation("Credit activation is switched off by tenant policy", code="CREDIT_NOT_ALLOWED")
        if purchase.cancelled_at is not None:
            raise BusinessRuleViolation("The purchase is cancelled", code="PURCHASE_CANCELLED")
        totals = purchase_totals(self._s, purchase)
        open_hours = purchase.hours - totals.net_activated
        if hours > open_hours:
            raise BusinessRuleViolation(
                f"Only {open_hours} hours of this purchase are not yet activated", code="EXCEEDS_UNACTIVATED_HOURS"
            )
        arrangement = self.arrangement(purchase.customer_id, purchase.currency)
        if arrangement is None:
            raise BusinessRuleViolation(
                "The customer has no approved credit arrangement in effect", code="NO_CREDIT_ARRANGEMENT"
            )
        value = quantize(hours * purchase.effective_rate, minor_units(self._s, purchase.currency))
        exposure = self.credit_exposure(purchase.customer_id, purchase.currency)
        if exposure + value > arrangement.limit_amount:
            raise BusinessRuleViolation(
                f"Credit limit {arrangement.limit_amount} {arrangement.currency} would be exceeded "
                f"(exposure {exposure}, this activation {value})",
                code="CREDIT_LIMIT_EXCEEDED",
            )
        entry = self._ledger.add(
            purchase,
            purchase.machine_id,
            T.ACTIVATED,
            hours,
            source=ActivationSource.CREDIT,
            expires_at=expiry_of(self._now, p.expiry_days),
            reason=reason,
            policy_version=self.eff.version_stamp,
        )
        self._record(
            "hours.credit_activated",
            purchase,
            {
                "hours": str(hours),
                "value": str(value),
                "arrangement_id": str(arrangement.id),
                "exposure_after": str(exposure + value),
                "entry_id": str(entry.id),
            },
            reason,
        )
        self._emit("CustomerHoursActivated", purchase, {"hours": str(hours), "source": "CREDIT"})
        self.cover_overruns(purchase.customer_id, purchase.machine_id)
        return entry

    def on_payment_decided(self, payment: CustomerPayment) -> None:
        """Verified: activate every purchase the payment is linked to. Rejected: release its purchase links (a
        claimed payment never activated anything, so nothing needs reversing)."""
        allocs = list(
            self._s.execute(
                select(HoursPaymentAllocation)
                .where(HoursPaymentAllocation.payment_id == payment.id, HoursPaymentAllocation.released_at.is_(None))
                .order_by(HoursPaymentAllocation.purchase_id)
            ).scalars()
        )
        if payment.status is SettlementStatus.REJECTED:
            for a in allocs:
                a.released_at, a.release_reason = self._now, "Payment rejected"
            self._s.flush()
            return
        if payment.status is SettlementStatus.VERIFIED:
            for a in allocs:
                self.activate_from_payments(self.lock_purchase(a.purchase_id), payment.id)

    # --- consumption ----------------------------------------------------------------------------------------
    def _candidates(self, customer_id: uuid.UUID, machine_id: uuid.UUID) -> list[HoursPurchase]:
        """The customer's open purchases with ledger activity on the machine, locked in FIFO (= lock) order."""
        on_machine = exists().where(
            HoursLedgerEntry.purchase_id == HoursPurchase.id, HoursLedgerEntry.machine_id == machine_id
        )
        return list(
            self._s.execute(
                select(HoursPurchase)
                .where(HoursPurchase.customer_id == customer_id, HoursPurchase.cancelled_at.is_(None), on_machine)
                .order_by(HoursPurchase.created_at, HoursPurchase.purchase_number)
                .with_for_update()
            ).scalars()
        )

    def _consume(self, wea: WorkExecutionAllocation, wanted: Decimal) -> Decimal:
        taken = ZERO
        for purchase in self._candidates(wea.customer_id, wea.machine_id):
            if taken >= wanted:
                break
            left = purchase_totals(self._s, purchase).remaining_on(wea.machine_id)
            take = min(left, wanted - taken)
            if take <= 0:
                continue
            self._ledger.add(
                purchase,
                wea.machine_id,
                T.CONSUMED,
                take,
                job_id=wea.job_id,
                allocation_id=wea.id,
                reason="Work execution allocation",
                policy_version=self.eff.version_stamp,
            )
            taken += take
        return taken

    def consumed_for(self, allocation_id: uuid.UUID) -> Decimal:
        return sum(
            (
                Decimal(h)
                for h in self._s.execute(
                    select(HoursLedgerEntry.hours).where(
                        HoursLedgerEntry.allocation_id == allocation_id, HoursLedgerEntry.entry_type == T.CONSUMED
                    )
                ).scalars()
            ),
            ZERO,
        )

    def check_start(self, job: Job) -> None:
        """START gate of a prepaid job (policy BLOCK_START): remaining activated hours on its machine."""
        if job.billing_mode is not BillingMode.PREPAID_HOURS:
            return
        if self.policy.over_consumption is not OverConsumption.BLOCK_START:
            return
        if available_hours(self._s, job_customer(self._s, job), job.machine_id) <= 0:
            raise BusinessRuleViolation(
                "The customer has no activated hours left on this machine", code="NO_AVAILABLE_HOURS"
            )

    def allocate_job(self, job: Job, billable: Decimal) -> WorkExecutionAllocation | None:
        """Work Execution Allocation on COMPLETE: consume the billable hours FIFO; hours beyond what is available are
        not consumed but raised as an HOURS_OVERRUN exception (cleared by new activation or a reviewed write-off).
        Hours the job held under daily drawdown (PROVISIONAL) are given back first and replaced by this final
        allocation, so the job's total always equals its billable hours."""
        if job.billing_mode is not BillingMode.PREPAID_HOURS:
            return None
        existing = self._s.execute(
            select(WorkExecutionAllocation).where(WorkExecutionAllocation.job_id == job.id)
        ).scalar_one_or_none()
        if existing is not None:
            return existing  # one allocation per job
        customer_id = job_customer(self._s, job)
        wea = WorkExecutionAllocation(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            job_id=job.id,
            customer_id=customer_id,
            machine_id=job.machine_id,
            billable_hours=billable,
            policy_version=self.eff.version_stamp,
            created_by=self._actor.user_id,
            created_at=self._now,
        )
        # The exception id must be known before the allocation row is written (append-only), so the plan comes first.
        candidates = self._candidates(customer_id, job.machine_id)
        open_ids = {p.id for p in candidates}
        held = sum((h for (pid, _, _), h in self.provisional_held(job.id).items() if pid in open_ids), ZERO)
        available = held + sum(
            (purchase_totals(self._s, p).remaining_on(job.machine_id) for p in candidates),
            ZERO,
        )
        excess = max(ZERO, billable - available)
        if excess > 0:
            wea.exception_id = self._overrun(job, billable, billable - excess, excess)
        self._s.add(wea)
        self._s.flush()
        released = self.release_provisional(job, "Replaced by the final allocation at completion", wea.id)
        self._close_daily_overrun(job, "Replaced by the final work execution allocation at completion")
        consumed = self._consume(wea, billable)
        self._audit.record(
            actor=self._actor,
            action="hours.work_allocated",
            entity_type="work_execution_allocation",
            entity_id=wea.id,
            tenant_id=self._tid,
            after={
                "job_id": str(job.id),
                "billable_hours": str(billable),
                "consumed": str(consumed),
                "overrun": str(billable - consumed),
                "provisional_replaced": str(released),
            },
            policy_version=self.eff.version_stamp[:64],
        )
        self.check_low_balance(customer_id, job.machine_id)
        return wea

    # --- daily drawdown (DEC-031 P1) ---------------------------------------------------------------------------
    def provisional_held(self, job_id: uuid.UUID) -> dict[tuple[uuid.UUID, uuid.UUID, date | None], Decimal]:
        """Net provisional hours the job holds, per (purchase, machine, usage day); zero entries left out."""
        held: dict[tuple[uuid.UUID, uuid.UUID, date | None], Decimal] = {}
        for pid, mid, day, t, hours in self._s.execute(
            select(
                HoursLedgerEntry.purchase_id,
                HoursLedgerEntry.machine_id,
                HoursLedgerEntry.usage_day,
                HoursLedgerEntry.entry_type,
                func.sum(HoursLedgerEntry.hours),
            )
            .where(
                HoursLedgerEntry.job_id == job_id,
                HoursLedgerEntry.entry_type.in_([T.PROVISIONAL, T.PROVISIONAL_REVERSED]),
            )
            .group_by(
                HoursLedgerEntry.purchase_id,
                HoursLedgerEntry.machine_id,
                HoursLedgerEntry.usage_day,
                HoursLedgerEntry.entry_type,
            )
        ):
            key = (pid, mid, day)
            held[key] = held.get(key, ZERO) - SIGN[t] * Decimal(hours)
        return {k: v for k, v in held.items() if v != 0}

    def draw_day(self, job: Job, customer_id: uuid.UUID, day: date, wanted: Decimal) -> Decimal:
        """Draw `wanted` hours of one day provisionally, FIFO over the customer's purchases on the job's machine;
        returns what could be drawn (the rest is the day's shortfall)."""
        taken = ZERO
        for purchase in self._candidates(customer_id, job.machine_id):
            if taken >= wanted:
                break
            take = min(purchase_totals(self._s, purchase).remaining_on(job.machine_id), wanted - taken)
            if take <= 0:
                continue
            self._ledger.add(
                purchase,
                job.machine_id,
                T.PROVISIONAL,
                take,
                job_id=job.id,
                reason=f"Daily drawdown {day.isoformat()}",
                policy_version=self.eff.version_stamp,
                usage_day=day,
            )
            taken += take
        return taken

    def give_back(
        self,
        job: Job,
        hours: Decimal,
        reason: str,
        *,
        day: date | None = None,
        allocation_id: uuid.UUID | None = None,
    ) -> Decimal:
        """Reverse provisional hours of the job (one day, or every day when `day` is None), newest purchase first."""
        held = sorted(
            ((k, v) for k, v in self.provisional_held(job.id).items() if day is None or k[2] == day),
            key=lambda kv: (str(kv[0][2]), str(kv[0][0])),
            reverse=True,
        )
        purchases = {
            p.id: p
            for p in self._s.execute(
                select(HoursPurchase).where(HoursPurchase.id.in_({k[0] for k, _ in held}))
            ).scalars()
        }
        left = hours
        for (pid, mid, usage_day), amount in held:
            if left <= 0:
                break
            back = min(amount, left)
            if back <= 0:
                continue
            self._ledger.add(
                purchases[pid],
                mid,
                T.PROVISIONAL_REVERSED,
                back,
                job_id=job.id,
                allocation_id=allocation_id,
                reason=reason,
                policy_version=self.eff.version_stamp,
                usage_day=usage_day,
            )
            left -= back
        return hours - max(left, ZERO)

    def release_provisional(self, job: Job, reason: str, allocation_id: uuid.UUID | None = None) -> Decimal:
        """Give back everything the job holds provisionally (completion, cancellation)."""
        total = sum(self.provisional_held(job.id).values(), ZERO)
        if total <= 0:
            return ZERO
        released = self.give_back(job, total, reason, allocation_id=allocation_id)
        self._audit.record(
            actor=self._actor,
            action="hours.provisional_released",
            entity_type="job",
            entity_id=job.id,
            tenant_id=self._tid,
            after={"hours": str(released), "allocation_id": str(allocation_id) if allocation_id else None},
            reason=reason,
            policy_version=self.eff.version_stamp[:64],
        )
        return released

    def daily_overrun(self, job: Job, day: date, wanted: Decimal, covered: Decimal) -> uuid.UUID:
        """The over-consumption rule applied the day it happens: a running job drew more than the customer has left.
        One exception per job (re-opened if it was covered and the job runs short again)."""
        key = f"{job.id}:{ExceptionType.HOURS_OVERRUN.value}:DAILY"
        row = self._s.execute(
            select(JobException).where(JobException.dedupe_key == key).with_for_update()
        ).scalar_one_or_none()
        excess = wanted - covered
        if row is not None:
            if row.status is not ExceptionStatus.OPEN:
                row.status, row.reviewed_by, row.reviewed_at = ExceptionStatus.OPEN, None, None
                row.review_note = f"Daily drawdown short again on {day.isoformat()}"
                self._s.flush()
                self._emit_overrun(row.id, job, wanted, excess, day)
            return row.id
        exc_id = uuid.uuid4()
        self._s.execute(
            insert(JobException)
            .values(
                id=exc_id,
                tenant_id=self._tid,
                job_id=job.id,
                machine_id=job.machine_id,
                meter_capture_id=None,
                exception_type=ExceptionType.HOURS_OVERRUN,
                severity="WARNING",
                blocking=self.policy.overrun_exception_blocking,
                dedupe_key=key,
                evidence={
                    "drawdown": "DAILY",
                    "day": day.isoformat(),
                    "billable_hours_to_date": str(wanted),
                    "covered_hours": str(covered),
                    "excess_hours": str(excess),
                },
                policy_version=self.eff.version_stamp,
                status=ExceptionStatus.OPEN,
                created_at=self._now,
            )
            .on_conflict_do_nothing()
        )
        self._emit_overrun(exc_id, job, wanted, excess, day)
        return exc_id

    def _close_daily_overrun(self, job: Job, note: str) -> bool:
        key = f"{job.id}:{ExceptionType.HOURS_OVERRUN.value}:DAILY"
        row = self._s.execute(
            select(JobException)
            .where(JobException.dedupe_key == key, JobException.status == ExceptionStatus.OPEN)
            .with_for_update()
        ).scalar_one_or_none()
        if row is None:
            return False
        row.status = ExceptionStatus.EXPLAINED
        row.reviewed_by, row.reviewed_at, row.review_note = self._actor.user_id, self._now, note
        self._s.flush()
        self._audit.record(
            actor=self._actor,
            action="hours.overrun_covered",
            entity_type="job_exception",
            entity_id=row.id,
            tenant_id=self._tid,
            before={"status": "OPEN"},
            after={"status": "EXPLAINED", "job_id": str(job.id), "note": note},
        )
        return True

    def cover_daily_overrun(self, job: Job) -> bool:
        return self._close_daily_overrun(job, "Covered by newly activated hours")

    def _emit_overrun(self, exc_id: uuid.UUID, job: Job, billable: Decimal, excess: Decimal, day: date) -> None:
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="CustomerHoursOverrun",
            key=str(job.machine_id),
            payload={
                "exception_id": str(exc_id),
                "job_id": str(job.id),
                "job_number": job.job_number,
                "machine_id": str(job.machine_id),
                "billable_hours": str(billable),
                "excess_hours": str(excess),
                "drawdown": "DAILY",
                "day": day.isoformat(),
            },
            tenant_id=self._tid,
        )

    # --- low balance (DEC-031 P2) ------------------------------------------------------------------------------
    def check_low_balance(self, customer_id: uuid.UUID, machine_id: uuid.UUID) -> None:
        """After hours left the balance: tell the office once when a purchase falls to the tenant's threshold."""
        if self.policy.low_balance_hours is None:
            return
        from asseta.modules.hours.low_balance import LowBalanceMonitor  # lazy: builds on the engine

        monitor = LowBalanceMonitor(self._s, self._tid, self._now, self.eff)
        for purchase in self._candidates(customer_id, machine_id):
            just_used = self._s.execute(
                select(HoursLedgerEntry.id)
                .where(
                    HoursLedgerEntry.purchase_id == purchase.id,
                    HoursLedgerEntry.occurred_at == self._now,
                    HoursLedgerEntry.entry_type.in_([T.CONSUMED, T.PROVISIONAL]),
                )
                .limit(1)
            ).first()
            monitor.check(purchase, after_deduction=just_used is not None)  # an empty purchase only if just used

    def _overrun(self, job: Job, billable: Decimal, covered: Decimal, excess: Decimal) -> uuid.UUID:
        exc_id = uuid.uuid4()
        self._s.execute(
            insert(JobException)
            .values(
                id=exc_id,
                tenant_id=self._tid,
                job_id=job.id,
                machine_id=job.machine_id,
                meter_capture_id=None,
                exception_type=ExceptionType.HOURS_OVERRUN,
                severity="WARNING",
                blocking=self.policy.overrun_exception_blocking,
                dedupe_key=f"{job.id}:{ExceptionType.HOURS_OVERRUN.value}",
                evidence={"billable_hours": str(billable), "covered_hours": str(covered), "excess_hours": str(excess)},
                policy_version=self.eff.version_stamp,
                status=ExceptionStatus.OPEN,
                created_at=self._now,
            )
            .on_conflict_do_nothing()
        )
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="CustomerHoursOverrun",
            key=str(job.machine_id),
            payload={
                "exception_id": str(exc_id),
                "job_id": str(job.id),
                "job_number": job.job_number,
                "machine_id": str(job.machine_id),
                "billable_hours": str(billable),
                "excess_hours": str(excess),
            },
            tenant_id=self._tid,
        )
        return exc_id

    def cover_overruns(self, customer_id: uuid.UUID, machine_id: uuid.UUID) -> None:
        """New hours on a machine first cover the customer's open overruns there (oldest first)."""
        rows = list(
            self._s.execute(
                select(WorkExecutionAllocation, JobException)
                .join(JobException, JobException.id == WorkExecutionAllocation.exception_id)
                .where(
                    WorkExecutionAllocation.customer_id == customer_id,
                    WorkExecutionAllocation.machine_id == machine_id,
                    JobException.status == ExceptionStatus.OPEN,
                )
                .order_by(WorkExecutionAllocation.created_at)
                .with_for_update(of=JobException)
            )
        )
        for wea, exc in rows:
            missing = wea.billable_hours - self.consumed_for(wea.id)
            if missing > 0:
                missing -= self._consume(wea, missing)
            if missing <= 0:
                exc.status = ExceptionStatus.EXPLAINED
                exc.reviewed_by, exc.reviewed_at = self._actor.user_id, self._now
                exc.review_note = "Covered by newly activated hours"
                self._s.flush()
                self._audit.record(
                    actor=self._actor,
                    action="hours.overrun_covered",
                    entity_type="job_exception",
                    entity_id=exc.id,
                    tenant_id=self._tid,
                    before={"status": "OPEN"},
                    after={"status": "EXPLAINED", "job_id": str(wea.job_id)},
                )


def resolve_billing_mode(
    session: Session, tenant_id: uuid.UUID, requested: BillingMode | None, at: datetime
) -> BillingMode:
    """The job's billing mode under tenant policy. With customer hours switched off every job is INVOICE (the
    behaviour before customer hours); asking for PREPAID_HOURS then is refused."""
    p = hours_policy(session, tenant_id, at).policy
    if not p.enabled:
        if requested is BillingMode.PREPAID_HOURS:
            raise BusinessRuleViolation("Customer hours are switched off for this tenant", code="HOURS_DISABLED")
        return BillingMode.INVOICE
    mode = requested or p.default_billing_mode
    if mode not in p.billing_modes:
        raise BusinessRuleViolation(
            f"Billing mode {mode.value} is not allowed by tenant policy", code="BILLING_MODE_NOT_ALLOWED"
        )
    return mode
