"""Petty cash reminders (DEC-033), run by the notification scheduler for tenants with PETTY_CASH on: a count overdue
(only when the tenant sets `count_every_days`), a fund below its low-balance level, an advance not cleared by its due
time. Read-only over the ledger; notifications are deduplicated per record and tenant-local day, so re-runs are
harmless."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.db import DbScope, apply_scope
from asseta.modules.finance.common import local_date, tenant_settings
from asseta.modules.notification.engine import NotificationEngine
from asseta.modules.notification.rules import Intent, perm, record_link, staff
from asseta.modules.notification.settings import get_notification_settings
from asseta.modules.pettycash.ledger import FundLedger
from asseta.modules.pettycash.models import AdvanceStatus, PettyCashAdvance, PettyCashFund
from asseta.modules.pettycash.permissions import MANAGE_CODE, PROPOSE_CODE
from asseta.modules.policy.capabilities import PETTY_CASH, capability_on
from asseta.modules.policy.service import PolicyService
from asseta.modules.tenancy.models import Tenant, TenantStatus

log = structlog.get_logger()
PETTY = "/tenant/finance/petty-cash"


@dataclass
class PettySweepSummary:
    tenants: int = 0
    notifications: int = 0
    failures: int = 0


def sweep_tenant(s: Session, tenant_id: uuid.UUID, now: datetime) -> list[Intent]:
    if not capability_on(s, tenant_id, PETTY_CASH, now):
        return []
    policy = PolicyService(s).petty_cash(tenant_id, at=now).policy
    day = local_date(tenant_settings(s, tenant_id).timezone, now).isoformat()
    ledger = FundLedger(s, now)
    intents: list[Intent] = []
    funds = list(s.execute(select(PettyCashFund).where(PettyCashFund.is_active.is_(True))).scalars())
    for fund in funds:
        link = record_link("petty_cash_fund", fund.id, PETTY)
        if policy.count_every_days is not None:
            last = ledger.last_count_at(fund.id) or fund.created_at
            if last + timedelta(days=policy.count_every_days) <= now:
                intents.append(
                    Intent(
                        "PETTY_CASH_COUNT_OVERDUE",
                        (staff(fund.holder_staff_id), perm(MANAGE_CODE)),
                        f"Petty cash count due — {fund.code}",
                        f"{fund.name} has not been counted for {policy.count_every_days} days or more; count it "
                        "(with a witness when your company asks for one).",
                        f"petty-count-due:{fund.id}:{day}",
                        link,
                        "petty_cash_fund",
                        str(fund.id),
                    )
                )
        if fund.low_balance_level is not None:
            balance = ledger.figures(fund).balance
            if balance < fund.low_balance_level:
                intents.append(
                    Intent(
                        "PETTY_CASH_FUND_LOW",
                        (staff(fund.holder_staff_id), perm(PROPOSE_CODE)),
                        f"Petty cash running low — {fund.code}",
                        f"{fund.name} holds {fund.currency} {balance}, below its level of {fund.currency} "
                        f"{fund.low_balance_level}. A top-up can be requested.",
                        f"petty-fund-low:{fund.id}:{day}",
                        link,
                        "petty_cash_fund",
                        str(fund.id),
                    )
                )
    holders = {f.id: f.holder_staff_id for f in funds}
    for adv in s.execute(
        select(PettyCashAdvance).where(
            PettyCashAdvance.status == AdvanceStatus.OUTSTANDING, PettyCashAdvance.due_at <= now
        )
    ).scalars():
        audience = (staff(adv.recipient_staff_id), *((staff(holders[adv.fund_id]),) if adv.fund_id in holders else ()))
        intents.append(
            Intent(
                "PETTY_CASH_ADVANCE_OVERDUE",
                audience,
                f"Cash advance not cleared — {adv.number}",
                f"The advance of {adv.currency} {adv.amount} was due to be cleared with receipts and change by "
                f"{adv.due_at:%Y-%m-%d}.",
                f"petty-advance-overdue:{adv.id}:{day}",
                record_link("petty_cash_advance", adv.id, PETTY),
                "petty_cash_advance",
                str(adv.id),
            )
        )
    return intents


def run_petty_cash_sweep(session_factory: Callable[[], Session], now: datetime) -> PettySweepSummary:
    """One pass over every non-closed tenant; one tenant's failure never blocks the others."""
    summary = PettySweepSummary()
    cfg = get_notification_settings()
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        tenants = list(s.execute(select(Tenant.id).where(Tenant.status != TenantStatus.CLOSED)).scalars())
    for tid in tenants:
        summary.tenants += 1
        try:
            with session_factory() as s, s.begin():
                apply_scope(s, DbScope.TENANT, tid, None)
                intents = sweep_tenant(s, tid, now)
                if intents:
                    apply_scope(s, DbScope.SYSTEM, None, None)
                    summary.notifications += len(NotificationEngine(s, now.date(), now, cfg).deliver(tid, intents))
        except Exception:
            log.exception("petty_cash_sweep_tenant_failed", tenant_id=str(tid))
            summary.failures += 1
    log.info("petty_cash_sweep_completed", **summary.__dict__)
    return summary
