"""Customer hours engine: activation (verified money / authorised credit only) and the low-balance check after hours
are used. Called from the hours service, the payment decision and machine-report approval (which consumes hours from
the orders); every write is a ledger entry plus an audit event."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.errors import BusinessRuleViolation, NotFound
from asseta.core.money import quantize
from asseta.core.outbox import OutboxWriter
from asseta.core.signals import sod_violation
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
)
from asseta.modules.platform_billing.models_commercial import Currency
from asseta.modules.policy.schemas import ActivationBasis, CustomerHoursPolicy
from asseta.modules.policy.service import EffectivePolicy, PolicyService

TOPIC = "asseta.hours"
T = LedgerEntryType


def hours_policy(session: Session, tenant_id: uuid.UUID, at: datetime) -> EffectivePolicy[CustomerHoursPolicy]:
    return PolicyService(session).customer_hours(tenant_id, at=at)


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

    @property
    def ledger(self) -> LedgerWriter:
        """The hours ledger writer (machine reports consume hours through it, ADR-008 §2)."""
        return self._ledger

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
    def activate_from_payments(
        self, purchase: HoursPurchase, payment_id: uuid.UUID | None = None, approved: bool = False
    ) -> Decimal:
        """Raise activated hours to what VERIFIED allocated money pays for (never anything else). Credit-activated
        hours count as already active: later payments settle them before activating more. A purchase that costs
        nothing activates only with a second person's approval (`approved`) unless the tenant waives it."""
        if purchase.cancelled_at is not None or ActivationBasis.VERIFIED_PAYMENT not in self.policy.activation_basis:
            return ZERO
        if purchase.amount <= 0 and self.policy.zero_amount_requires_approval and not approved:
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
            reason="Approved: nothing to pay" if purchase.amount <= 0 else "Verified payment",
            policy_version=self.eff.version_stamp,
        )
        self._record(
            "hours.activated",
            purchase,
            {"hours": str(new), "source": "PAYMENT", "verified_amount": str(verified), "entry_id": str(entry.id)},
        )
        self._emit("CustomerHoursActivated", purchase, {"hours": str(new), "source": "PAYMENT"})
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
        if purchase.created_by is not None and purchase.created_by == self._actor.user_id:
            sod_violation(self._tid, self._actor.user_id, "credit_activate", "hours_purchase", purchase.id)
            raise BusinessRuleViolation(
                "The person who recorded a purchase cannot activate it on credit", code="SEGREGATION_OF_DUTIES"
            )
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
                    HoursLedgerEntry.entry_type == T.CONSUMED,
                )
                .limit(1)
            ).first()
            monitor.check(purchase, after_deduction=just_used is not None)  # an empty purchase only if just used
