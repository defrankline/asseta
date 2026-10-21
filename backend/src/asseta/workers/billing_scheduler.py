"""Billing scheduler: periodically generates due platform invoices and re-evaluates entitlements for every
billable subscription. Idempotent (unique invoice per period; deterministic entitlement rules), so it can run
hourly and after outages without duplicates. Each subscription is processed in its own transaction."""

import signal
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor
from asseta.core.clock import system_clock
from asseta.core.config import get_settings
from asseta.core.correlation import set_correlation_id
from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.core.logging import configure_logging
from asseta.modules.platform_billing.enums import BILLABLE_STATUSES
from asseta.modules.platform_billing.invoice_service import InvoiceService
from asseta.modules.platform_billing.models_commercial import TenantSubscription
from asseta.modules.platform_billing.repository import BillingRepository
from asseta.modules.platform_billing.subscription_service import SubscriptionService

log = structlog.get_logger()
ACTOR = AuditActor(user_id=None, roles=["system:billing-scheduler"], source="worker")


@dataclass
class CycleSummary:
    subscriptions: int = 0
    invoices_created: int = 0
    entitlement_changes: int = 0
    failures: list[str] = field(default_factory=list)


def _billable_ids(session_factory: Callable[[], Session]) -> list[uuid.UUID]:
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.PLATFORM, None, None)
        return list(
            s.execute(
                select(TenantSubscription.id)
                .where(TenantSubscription.status.in_(BILLABLE_STATUSES))
                .order_by(TenantSubscription.created_at)
            ).scalars()
        )


def run_billing_cycle(today: date, session_factory: Callable[[], Session] | None = None) -> CycleSummary:
    factory = session_factory or get_sessionmaker()
    summary = CycleSummary()
    for sid in _billable_ids(factory):
        set_correlation_id(str(uuid.uuid4()))
        summary.subscriptions += 1
        try:
            with factory() as s, s.begin():
                apply_scope(s, DbScope.PLATFORM, None, None)
                summary.invoices_created += len(InvoiceService(s, ACTOR).generate_due(sid, today, today).created)
            with factory() as s, s.begin():
                apply_scope(s, DbScope.PLATFORM, None, None)
                sub = BillingRepository(s).subscription(sid, for_update=True)
                summary.entitlement_changes += int(
                    SubscriptionService(s, ACTOR).evaluate_entitlement(sub, today).changed
                )
        except Exception as exc:  # isolate one tenant's failure from the rest of the run
            log.exception("billing_cycle_subscription_failed", subscription_id=str(sid))
            summary.failures.append(f"{sid}: {type(exc).__name__}")
    log.info("billing_cycle_completed", **summary.__dict__)
    return summary


def run() -> None:
    configure_logging()
    interval = get_settings().billing_scheduler_interval_seconds
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping:
        run_billing_cycle(system_clock().date())
        deadline = time.monotonic() + interval
        while not stopping and time.monotonic() < deadline:
            time.sleep(1)
