"""Low-balance warning (DEC-031 P2, `CUSTOMER_HOURS.low_balance_hours`; null = off).

A purchase *crosses* when its remaining hours fall to the threshold while the customer has no more than the threshold
left on that machine (a newer purchase still covering the work is not a reason to warn). Each crossing is one
`hours_low_balance_alert` row and one HOURS_LOW_BALANCE notification to the office (holders of `tenant.hours.read`);
the alert re-arms when the purchase is back above the threshold. When `low_balance_notify_customer` is on, the
customer's contact phone also gets one SMS per crossing through the tenant's SMS channel (and its SMS credits).

Crossings are detected right after hours leave the balance (completion, daily drawdown, expiry) and by the scheduler
sweep (threshold changes, re-arming). A purchase already used up before the tenant set a threshold is never warned
about retroactively: the sweep only considers purchases that still have hours left."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.outbox import OutboxWriter
from asseta.core.sms.msisdn import normalize_msisdn
from asseta.modules.fleet.models import Machine
from asseta.modules.hours.ledger import ZERO, purchase_totals
from asseta.modules.hours.models import HoursLowBalanceAlert, HoursPurchase
from asseta.modules.jobs.models import Customer
from asseta.modules.notification.models import DeliveryStatus, SmsDelivery
from asseta.modules.notification.segments import sms_segments
from asseta.modules.notification.types import Severity
from asseta.modules.policy.schemas import CustomerHoursPolicy
from asseta.modules.policy.service import EffectivePolicy
from asseta.modules.tenancy.models import Tenant

TOPIC = "asseta.hours"
SWEEP = AuditActor(None, [], "scheduler")
SMS_NOT_REQUESTED, SMS_PENDING, SMS_QUEUED, SMS_NO_PHONE = "NOT_REQUESTED", "PENDING", "QUEUED", "NO_PHONE"


def _available(s: Session, customer_id: uuid.UUID, machine_id: uuid.UUID) -> Decimal:
    from asseta.modules.hours.engine import available_hours  # lazy: the engine imports this module's monitor

    return available_hours(s, customer_id, machine_id)


class LowBalanceMonitor:
    def __init__(
        self, s: Session, tenant_id: uuid.UUID, now: datetime, eff: EffectivePolicy[CustomerHoursPolicy]
    ) -> None:
        self._s, self._tid, self._now, self._eff = s, tenant_id, now, eff

    @property
    def policy(self) -> CustomerHoursPolicy:
        return self._eff.policy

    def _armed(self, purchase_id: uuid.UUID) -> HoursLowBalanceAlert | None:
        return self._s.execute(
            select(HoursLowBalanceAlert)
            .where(HoursLowBalanceAlert.purchase_id == purchase_id, HoursLowBalanceAlert.rearmed_at.is_(None))
            .with_for_update()
        ).scalar_one_or_none()

    def check(self, purchase: HoursPurchase, *, after_deduction: bool) -> HoursLowBalanceAlert | None:
        threshold = self.policy.low_balance_hours if self.policy.enabled else None
        armed = self._armed(purchase.id)
        totals = purchase_totals(self._s, purchase)
        remaining = totals.remaining
        if armed is not None:
            if threshold is None or remaining > threshold:
                armed.rearmed_at = self._now  # back above the threshold (or warnings switched off): re-arm
                self._s.flush()
            return None
        if threshold is None or purchase.cancelled_at is not None or totals.activated <= 0 or remaining > threshold:
            return None
        if remaining <= 0 and not after_deduction:
            return None  # used up before: never warned about retroactively
        available = _available(self._s, purchase.customer_id, purchase.machine_id)
        if available > threshold:
            return None  # other hours of the customer still cover this machine
        sequence = (
            self._s.execute(
                select(func.coalesce(func.max(HoursLowBalanceAlert.sequence), 0)).where(
                    HoursLowBalanceAlert.purchase_id == purchase.id
                )
            ).scalar_one()
            + 1
        )
        notify = self.policy.low_balance_notify_customer
        alert = HoursLowBalanceAlert(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            purchase_id=purchase.id,
            customer_id=purchase.customer_id,
            machine_id=purchase.machine_id,
            sequence=sequence,
            threshold_hours=threshold,
            remaining_hours=max(remaining, ZERO),
            available_hours=max(available, ZERO),
            crossed_at=self._now,
            notify_customer=notify,
            customer_sms_status=SMS_PENDING if notify else SMS_NOT_REQUESTED,
            policy_version=self._eff.version_stamp,
            created_at=self._now,
        )
        self._s.add(alert)
        self._s.flush()
        AuditService(self._s).record(
            actor=SWEEP,
            action="hours.low_balance",
            entity_type="hours_purchase",
            entity_id=purchase.id,
            tenant_id=self._tid,
            after={
                "purchase_number": purchase.purchase_number,
                "alert_id": str(alert.id),
                "remaining_hours": str(alert.remaining_hours),
                "available_hours": str(alert.available_hours),
                "threshold_hours": str(threshold),
                "notify_customer": notify,
            },
            policy_version=self._eff.version_stamp[:64],
        )
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="CustomerHoursLowBalance",
            key=str(purchase.customer_id),
            payload={
                "alert_id": str(alert.id),
                "purchase_id": str(purchase.id),
                "purchase_number": purchase.purchase_number,
                "customer_id": str(purchase.customer_id),
                "machine_id": str(purchase.machine_id),
                "remaining_hours": str(alert.remaining_hours),
                "available_hours": str(alert.available_hours),
                "threshold_hours": str(threshold),
            },
            tenant_id=self._tid,
        )
        return alert

    def sweep(self) -> int:
        """Re-arm alerts back above the threshold and warn purchases with hours left that are at or below it."""
        made = 0
        armed_ids = set(
            self._s.execute(
                select(HoursLowBalanceAlert.purchase_id).where(HoursLowBalanceAlert.rearmed_at.is_(None))
            ).scalars()
        )
        stmt = select(HoursPurchase).where(HoursPurchase.cancelled_at.is_(None))
        if self.policy.low_balance_hours is None or not self.policy.enabled:
            if not armed_ids:
                return 0
            stmt = stmt.where(HoursPurchase.id.in_(armed_ids))
        for purchase in self._s.execute(stmt.order_by(HoursPurchase.id)).scalars():
            if self.check(purchase, after_deduction=False) is not None:
                made += 1
        return made


def queue_customer_sms(
    s: Session, tenant_id: uuid.UUID, now: datetime, default_country_code: str, max_chars: int
) -> int:
    """SMS the customer's contact phone for crossings that asked for it (system scope: SMS rows are system-written).
    Billable to the tenant's SMS wallet; quiet hours, rate limits and credits are handled by the SMS dispatcher."""
    queued = 0
    tenant = s.get(Tenant, tenant_id)
    sender = tenant.display_name if tenant else "Asseta"
    for alert in s.execute(
        select(HoursLowBalanceAlert)
        .where(HoursLowBalanceAlert.tenant_id == tenant_id, HoursLowBalanceAlert.customer_sms_status == SMS_PENDING)
        .with_for_update(skip_locked=True)
    ).scalars():
        customer = s.get(Customer, alert.customer_id)
        machine = s.get(Machine, alert.machine_id)
        msisdn = None
        if customer is not None and customer.contact_phone:
            try:
                msisdn = normalize_msisdn(customer.contact_phone, default_country_code)
            except ValueError:
                msisdn = None
        if msisdn is None:
            alert.customer_sms_status = SMS_NO_PHONE
            continue
        label = f"{machine.asset_code}" if machine else "your machine"
        hours = f"{alert.available_hours.normalize():f}"
        text = (
            f"{sender}: {customer.name if customer else 'Customer'}, you have {hours} prepaid hours left on {label}. "
            "Please top up to keep the machine working."
        )
        if len(text) > max_chars:
            text = text[: max_chars - 1] + "…"
        delivery = SmsDelivery(
            id=uuid.uuid4(),
            notification_id=None,
            tenant_id=tenant_id,
            recipient_user_id=None,
            notification_type="HOURS_LOW_BALANCE",
            severity=Severity.WARNING,
            msisdn=msisdn,
            text=text,
            segments=sms_segments(text)[0],
            billable=True,
            status=DeliveryStatus.PENDING,
            attempts=0,
            next_attempt_at=now,
            created_at=now,
            updated_at=now,
        )
        s.add(delivery)
        alert.customer_sms_status, alert.customer_sms_id = SMS_QUEUED, delivery.id
        queued += 1
    s.flush()
    return queued
