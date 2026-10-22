"""SMS channel on top of `asseta.core.sms` (DEC-022). Each due delivery is handled in its own transaction:
quiet hours (tenant-local; CRITICAL bypasses) -> per-number rate limit -> tenant wallet debit per segment (idempotent
per delivery id; empty wallet = REFUSED_NO_CREDIT + in-app notice to the tenant owners) -> send with the delivery id
as provider `reference` -> retry with exponential backoff, or FAILED with the debit refunded. Platform staff SMS is
never tenant-billed. Delivery is at-least-once (a crash between send and commit re-sends the same reference)."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.core.db import DbScope, apply_scope
from asseta.core.sms import InvalidMsisdn, SmsClient, SmsSendError
from asseta.modules.notification.engine import NotificationEngine
from asseta.modules.notification.models import DeliveryStatus, SmsDelivery
from asseta.modules.notification.realtime import RealtimePublisher
from asseta.modules.notification.rules import Intent, perm
from asseta.modules.notification.settings import NotificationSettings, get_notification_settings
from asseta.modules.notification.types import Severity
from asseta.modules.platform_billing.enums import SmsWalletEntryType
from asseta.modules.platform_billing.sms_wallet import InsufficientSmsCredits, SmsWalletService
from asseta.modules.tenancy.models import TenantSettings

log = structlog.get_logger()
RATE_LIMIT_DEFER = timedelta(minutes=15)
REFERENCE = "sms_delivery"


@dataclass
class DispatchSummary:
    sent: int = 0
    retried: int = 0
    failed: int = 0
    deferred: int = 0
    refused: int = 0


def in_quiet_hours(local: datetime, start: int, end: int) -> bool:
    h = local.hour
    return (h >= start or h < end) if start > end else start <= h < end


def quiet_hours_end(local: datetime, end: int) -> datetime:
    candidate = datetime.combine(local.date(), time(end), local.tzinfo)
    return candidate if candidate > local else candidate + timedelta(days=1)


class SmsDispatcher:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        client: SmsClient,
        clock: Callable[[], datetime],
        publisher: RealtimePublisher | None = None,
        settings: NotificationSettings | None = None,
    ):
        self._factory, self._client, self._clock, self._publisher = session_factory, client, clock, publisher
        self._settings = settings or get_notification_settings()

    def dispatch_due(self, limit: int = 100) -> DispatchSummary:
        summary = DispatchSummary()
        now = self._clock()
        with self._factory() as s, s.begin():
            apply_scope(s, DbScope.SYSTEM, None, None)
            ids = list(
                s.execute(
                    select(SmsDelivery.id)
                    .where(SmsDelivery.status == DeliveryStatus.PENDING, SmsDelivery.next_attempt_at <= now)
                    .order_by(SmsDelivery.next_attempt_at)
                    .limit(limit)
                ).scalars()
            )
        for delivery_id in ids:
            self.dispatch_one(delivery_id, summary)
        return summary

    def dispatch_one(self, delivery_id: uuid.UUID, summary: DispatchSummary | None = None) -> DeliveryStatus | None:
        summary = summary or DispatchSummary()
        now = self._clock()
        engine: NotificationEngine | None = None
        with self._factory() as s, s.begin():
            apply_scope(s, DbScope.SYSTEM, None, None)
            d = s.execute(
                select(SmsDelivery)
                .where(SmsDelivery.id == delivery_id, SmsDelivery.status == DeliveryStatus.PENDING)
                .with_for_update(skip_locked=True)
            ).scalar_one_or_none()
            if d is None:
                return None  # another dispatcher has it, or it is already final
            engine = NotificationEngine(s, now.date(), now, self._settings)
            self._handle(s, d, now, summary, engine)
            d.updated_at = now
            status = d.status
        if engine is not None and self._publisher is not None:
            engine.publish(self._publisher)
        return status

    def _tz(self, s: Session, d: SmsDelivery) -> ZoneInfo:
        name = self._settings.platform_timezone
        if d.tenant_id is not None:
            ts = s.get(TenantSettings, d.tenant_id)
            name = ts.timezone if ts else name
        return ZoneInfo(name)

    def _handle(
        self, s: Session, d: SmsDelivery, now: datetime, summary: DispatchSummary, engine: NotificationEngine
    ) -> None:
        cfg = self._settings
        local = now.astimezone(self._tz(s, d))
        if d.severity is not Severity.CRITICAL and in_quiet_hours(local, cfg.quiet_hours_start, cfg.quiet_hours_end):
            d.next_attempt_at, d.last_error = quiet_hours_end(local, cfg.quiet_hours_end), "Deferred: quiet hours"
            summary.deferred += 1
            return
        recent = s.execute(
            select(func.count()).where(
                SmsDelivery.msisdn == d.msisdn,
                SmsDelivery.status == DeliveryStatus.SENT,
                SmsDelivery.sent_at > now - timedelta(hours=1),
            )
        ).scalar_one()
        if recent >= cfg.sms_rate_limit_per_hour:
            d.next_attempt_at, d.last_error = now + RATE_LIMIT_DEFER, "Deferred: rate limit"
            summary.deferred += 1
            return
        wallet = SmsWalletService(s)
        if d.billable and d.tenant_id is not None:
            try:
                posting = wallet.post(
                    d.tenant_id, SmsWalletEntryType.SMS_DEBIT, -d.segments, REFERENCE, d.id, d.notification_type
                )
            except InsufficientSmsCredits:
                d.status, d.last_error = DeliveryStatus.REFUSED_NO_CREDIT, "Tenant SMS wallet is empty"
                summary.refused += 1
                self._wallet_notice(engine, d.tenant_id, local, empty=True)
                return
            low = cfg.sms_wallet_low_threshold
            if posting.created and posting.entry.balance_after < low <= posting.entry.balance_after + d.segments:
                self._wallet_notice(engine, d.tenant_id, local, empty=False, balance=posting.entry.balance_after)
        d.attempts += 1
        try:
            result = self._client.send([d.msisdn], d.text, reference=str(d.id))
        except InvalidMsisdn:
            d.status, d.last_error = DeliveryStatus.INVALID_NUMBER, "Invalid phone number"
            self._refund(wallet, d)
            summary.failed += 1
            return
        except SmsSendError as exc:
            self._failed(wallet, d, now, str(exc), exc.retryable, summary)
            return
        except Exception as exc:  # transport surprises are treated as transient
            self._failed(wallet, d, now, f"SMS provider error: {type(exc).__name__}", True, summary)
            return
        d.status, d.sent_at, d.provider, d.last_error = DeliveryStatus.SENT, now, result.provider, None
        summary.sent += 1

    def _failed(
        self, wallet: SmsWalletService, d: SmsDelivery, now: datetime, error: str, retryable: bool, s: DispatchSummary
    ) -> None:
        d.last_error = error[:500]
        if retryable and d.attempts < self._settings.sms_max_attempts:
            d.next_attempt_at = now + timedelta(seconds=self._settings.sms_retry_base_seconds * 2 ** (d.attempts - 1))
            s.retried += 1
            return
        d.status = DeliveryStatus.FAILED
        self._refund(wallet, d)
        s.failed += 1
        log.warning("sms_delivery_failed", delivery_id=str(d.id), attempts=d.attempts)

    def _refund(self, wallet: SmsWalletService, d: SmsDelivery) -> None:
        if d.tenant_id is not None and wallet.existing(SmsWalletEntryType.SMS_DEBIT, d.id) is not None:
            wallet.post(d.tenant_id, SmsWalletEntryType.SMS_REFUND, d.segments, REFERENCE, d.id, "Delivery failed")

    def _wallet_notice(
        self, engine: NotificationEngine, tenant_id: uuid.UUID, local: datetime, empty: bool, balance: int = 0
    ) -> None:
        if empty:
            intent = Intent(
                "SMS_WALLET_EMPTY",
                (perm("tenant.billing.read"),),
                "SMS credits used up",
                "SMS notifications are paused until you buy an SMS bundle. In-app notifications continue.",
                f"wallet-empty:{tenant_id}:{local.date()}",
                "/tenant/sms-wallet",
                "sms_wallet",
                str(tenant_id),
            )
        else:
            intent = Intent(
                "SMS_WALLET_LOW",
                (perm("tenant.billing.read"),),
                "SMS credits running low",
                f"{balance} SMS credits left. Buy a bundle to keep SMS notifications flowing.",
                f"wallet-low:{tenant_id}:{local.date()}",
                "/tenant/sms-wallet",
                "sms_wallet",
                str(tenant_id),
            )
        engine.deliver(tenant_id, [intent])
