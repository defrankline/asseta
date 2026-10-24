"""Scheduled expiry sweep (tenant policy `expiry_days`, counted from each activation): writes EXPIRED ledger entries
for unused activated hours past their expiry and warns before it happens (`expiry_warning_days`). Idempotent: an
expired lot is never expired twice (FIFO over lots), warnings are deduplicated per purchase and expiry date."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import DbScope, apply_scope
from asseta.core.outbox import OutboxWriter
from asseta.modules.hours.engine import TOPIC, hours_policy
from asseta.modules.hours.ledger import ZERO, LedgerWriter, due_to_expire, next_expiry, purchase_totals
from asseta.modules.hours.models import HoursLedgerEntry, HoursPurchase, LedgerEntryType
from asseta.modules.notification.engine import NotificationEngine
from asseta.modules.notification.rules import Intent, perm
from asseta.modules.notification.settings import get_notification_settings
from asseta.modules.tenancy.models import Tenant, TenantSettings, TenantStatus

log = structlog.get_logger()
SWEEP = AuditActor(None, [], "scheduler")


@dataclass
class ExpirySummary:
    tenants: int = 0
    expired_entries: int = 0
    warnings: int = 0
    failures: int = 0


def _open_purchases(s: Session) -> list[HoursPurchase]:
    """Purchases with at least one activation lot that can expire, locked in a fixed order."""
    has_lots = (
        select(HoursLedgerEntry.purchase_id)
        .where(HoursLedgerEntry.entry_type == LedgerEntryType.ACTIVATED, HoursLedgerEntry.expires_at.is_not(None))
        .distinct()
    )
    return list(
        s.execute(
            select(HoursPurchase)
            .where(HoursPurchase.cancelled_at.is_(None), HoursPurchase.id.in_(has_lots))
            .order_by(HoursPurchase.id)
            .with_for_update()
        ).scalars()
    )


def sweep_tenant(s: Session, tenant_id: uuid.UUID, now: datetime) -> tuple[int, list[Intent]]:
    """Expire due hours of one tenant (inside its RLS scope); returns (entries written, warning intents)."""
    eff = hours_policy(s, tenant_id, now)
    ledger = LedgerWriter(s, tenant_id, None, now)
    audit = AuditService(s)
    written, intents = 0, []
    warn_until = now + timedelta(days=eff.policy.expiry_warning_days)
    ts = s.get(TenantSettings, tenant_id)
    tz = ZoneInfo(ts.timezone if ts else "UTC")
    for purchase in _open_purchases(s):
        totals = purchase_totals(s, purchase)
        due = due_to_expire(s, purchase, totals, now)
        if due > 0:
            left = due
            machines = sorted(
                totals.machines.items(), key=lambda kv: (kv[0] != purchase.machine_id, str(kv[0]))
            )  # the purchase's own machine first, then transfer targets
            for machine_id, m in machines:
                take = min(left, m.remaining)
                if take <= 0:
                    continue
                ledger.add(
                    purchase,
                    machine_id,
                    LedgerEntryType.EXPIRED,
                    take,
                    reason="Unused hours past the tenant expiry period",
                    policy_version=eff.version_stamp,
                )
                written += 1
                left -= take
                if left <= 0:
                    break
            audit.record(
                actor=SWEEP,
                action="hours.expired",
                entity_type="hours_purchase",
                entity_id=purchase.id,
                tenant_id=tenant_id,
                after={"purchase_number": purchase.purchase_number, "hours": str(due - max(left, ZERO))},
                policy_version=eff.version_stamp[:64],
            )
            OutboxWriter(s).emit(
                topic=TOPIC,
                event_type="CustomerHoursExpired",
                key=str(purchase.customer_id),
                payload={
                    "purchase_id": str(purchase.id),
                    "purchase_number": purchase.purchase_number,
                    "customer_id": str(purchase.customer_id),
                    "machine_id": str(purchase.machine_id),
                    "hours": str(due - max(left, ZERO)),
                },
                tenant_id=tenant_id,
            )
            totals = purchase_totals(s, purchase)
        soon = next_expiry(s, purchase.id, now)
        if soon is None or soon > warn_until or eff.policy.expiry_warning_days <= 0:
            continue
        expiring = due_to_expire(s, purchase, totals, soon)
        if expiring <= 0:
            continue
        local_day = soon.astimezone(tz).date().isoformat()
        intents.append(
            Intent(
                "HOURS_EXPIRING",
                (perm("tenant.hours.read"),),
                f"Hours expiring — {purchase.purchase_number}",
                f"{expiring} unused hours of {purchase.purchase_number} expire on {local_day}.",
                f"hours-expiring:{purchase.id}:{local_day}",
                f"/tenant/hours/purchases/{purchase.id}",
                "hours_purchase",
                str(purchase.id),
                data={"hours": str(expiring), "expires_on": local_day},
            )
        )
    return written, intents


def run_hours_expiry(session_factory: Callable[[], Session], now: datetime) -> ExpirySummary:
    """One sweep over every non-closed tenant; one tenant's failure never blocks the others."""
    summary = ExpirySummary()
    cfg = get_notification_settings()
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        tenants = list(s.execute(select(Tenant.id).where(Tenant.status != TenantStatus.CLOSED)).scalars())
    for tid in tenants:
        summary.tenants += 1
        try:
            with session_factory() as s, s.begin():
                apply_scope(s, DbScope.TENANT, tid, None)
                written, intents = sweep_tenant(s, tid, now)
                summary.expired_entries += written
                if intents:
                    apply_scope(s, DbScope.SYSTEM, None, None)
                    summary.warnings += len(NotificationEngine(s, now.date(), now, cfg).deliver(tid, intents))
        except Exception:
            log.exception("hours_expiry_tenant_failed", tenant_id=str(tid))
            summary.failures += 1
    log.info("hours_expiry_completed", **summary.__dict__)
    return summary
