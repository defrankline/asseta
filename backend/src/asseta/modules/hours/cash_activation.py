"""When the cash part of an hours sale counts as verified (CUSTOMER_HOURS policy `cash_activation`).

VERIFY (default, as before): a person other than the recorder verifies the cash payment.
ON_HANDOVER: when the office confirms a custodian's cash handover, the cash payments of hours sales that handover
    covers are verified by the system: the custodian's cash is handed over oldest first (the custody ledger's FIFO), so
    a short handover covers only the oldest. A payment the confirming person recorded is left for someone else.
ON_RECORDING: a cash payment recorded on an hours sale counts as verified when recorded; the custodian stays
    accountable through cash custody (outstanding balance, remittance cut-off and variances are unchanged).

Only cash payments linked to hours purchases (and not to invoices) qualify; bank and mobile money always keep the
manual verification. A system verification runs the same consequences as a person's: hours activate (in part, under
partial activation) and a job booked with the sale may be approved by policy. Each is audited and recorded in
`payment_auto_verification`. Custody figures do not move: a collection counts in custody whatever its status."""

import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.outbox import OutboxWriter
from asseta.modules.finance.models import (
    CashHandover,
    CustomerPayment,
    HirePaymentAllocation,
    HirePaymentMethod,
    SettlementStatus,
)
from asseta.modules.fleet.models import StaffMember
from asseta.modules.hours.engine import HoursEngine, hours_policy
from asseta.modules.hours.models import HoursPaymentAllocation, PaymentAutoVerification
from asseta.modules.policy.schemas import CashActivation as Mode

SYSTEM_ACTOR = AuditActor(None, ["system:policy"], "policy")
FINANCE_TOPIC = "asseta.finance"


def hours_cash(session: Session, payment: CustomerPayment) -> bool:
    """A claimed cash payment that pays hours purchases only (no invoice allocation): the policy may verify it."""
    if (
        payment.method is not HirePaymentMethod.CASH
        or payment.status is not SettlementStatus.CLAIMED
        or payment.reversed_at is not None
    ):
        return False
    linked = session.execute(
        select(HoursPaymentAllocation.id)
        .where(HoursPaymentAllocation.payment_id == payment.id, HoursPaymentAllocation.released_at.is_(None))
        .limit(1)
    ).first()
    invoiced = session.execute(
        select(HirePaymentAllocation.id)
        .where(HirePaymentAllocation.payment_id == payment.id, HirePaymentAllocation.released_at.is_(None))
        .limit(1)
    ).first()
    return linked is not None and invoiced is None


def verified_by_handover(session: Session, payment: CustomerPayment, at: datetime) -> bool:
    """The office does not verify this payment: the tenant verifies it when the handover covering it is confirmed."""
    return (
        hours_cash(session, payment)
        and hours_policy(session, payment.tenant_id, at).policy.cash_activation is Mode.ON_HANDOVER
    )


class CashActivation:
    def __init__(self, session: Session, tenant_id: uuid.UUID, decider: uuid.UUID | None, now: datetime):
        self._s, self._tid, self._decider, self._now = session, tenant_id, decider, now
        self._eff = hours_policy(session, tenant_id, now)

    @property
    def mode(self) -> Mode:
        return self._eff.policy.cash_activation

    def on_recorded(self, payment_id: uuid.UUID) -> bool:
        """ON_RECORDING: the cash payment just recorded on an hours sale counts as verified."""
        if self.mode is not Mode.ON_RECORDING:
            return False
        payment = self._lock(payment_id)
        if payment is None or not hours_cash(self._s, payment):
            return False
        holder = self._staff_name(payment.received_by_staff_id) or "the custodian"
        self._verify(
            payment,
            Mode.ON_RECORDING,
            f"Cash accepted on recording (policy); held by {holder} until handed over",
            None,
        )
        return True

    def on_handover_confirmed(self, handover: CashHandover, covered: Callable[[], list[uuid.UUID]]) -> list[uuid.UUID]:
        """ON_HANDOVER: verify the hours-sale cash payments the confirmed handover covers (`covered`: the custody
        ledger's FIFO, oldest first, up to the amount received)."""
        if self.mode is not Mode.ON_HANDOVER:
            return []
        done = []
        for payment_id in covered():
            payment = self._lock(payment_id)
            if payment is None or not hours_cash(self._s, payment):
                continue
            if payment.recorded_by is not None and payment.recorded_by == self._decider:
                continue  # the person confirming the handover recorded it: someone else verifies it
            self._verify(
                payment,
                Mode.ON_HANDOVER,
                f"Verified by the confirmed cash handover {handover.remittance_number}",
                handover.id,
            )
            done.append(payment.id)
        return done

    def _lock(self, payment_id: uuid.UUID) -> CustomerPayment | None:
        return self._s.execute(
            select(CustomerPayment).where(CustomerPayment.id == payment_id).with_for_update()
        ).scalar_one_or_none()

    def _staff_name(self, staff_id: uuid.UUID | None) -> str | None:
        if staff_id is None:
            return None
        return self._s.execute(select(StaffMember.full_name).where(StaffMember.id == staff_id)).scalar_one_or_none()

    def _verify(self, payment: CustomerPayment, mode: Mode, reason: str, handover_id: uuid.UUID | None) -> None:
        payment.status = SettlementStatus.VERIFIED
        payment.verified_by, payment.verified_at, payment.decision_note = None, self._now, reason
        self._s.flush()
        self._s.add(
            PaymentAutoVerification(
                id=uuid.uuid4(),
                tenant_id=self._tid,
                payment_id=payment.id,
                mode=mode.value,
                handover_id=handover_id,
                custodian_staff_id=payment.received_by_staff_id,
                policy_version=self._eff.version_stamp[:64],
                created_at=self._now,
            )
        )
        self._s.flush()
        AuditService(self._s).record(
            actor=SYSTEM_ACTOR,
            action="finance.payment.verified",
            entity_type="customer_payment",
            entity_id=payment.id,
            tenant_id=self._tid,
            before={"status": "CLAIMED"},
            after={
                "status": "VERIFIED",
                "amount": str(payment.amount),
                "currency": payment.currency,
                "verified_automatically": mode.value,
                "handover_id": str(handover_id) if handover_id else None,
            },
            reason=reason,
            policy_version=self._eff.version_stamp[:64],
        )
        # Same consequences as a person's verification: hours activate, approval may follow the money.
        HoursEngine(self._s, self._tid, SYSTEM_ACTOR, self._now).on_payment_decided(payment)
        OutboxWriter(self._s).emit(
            topic=FINANCE_TOPIC,
            event_type="CustomerPaymentVerified",
            key=str(payment.customer_id),
            payload={
                "payment_id": str(payment.id),
                "customer_id": str(payment.customer_id),
                "amount": str(payment.amount),
                "currency": payment.currency,
                "method": payment.method.value,
                "verified_automatically": mode.value,
            },
            tenant_id=self._tid,
        )
