"""Daily remittance cut-off (tenant policy `cash.remittance_cutoff_hour`, tenant-local; null = off). A scheduled
sweep, modelled on the engine-hours daily-report check: once the cut-off of the tenant-local day has passed, every
custodian still holding unremitted cash that they already held before the cut-off is flagged once for that day
(`cash_remittance_overdue`, unique per custodian per day) and REMITTANCE_OVERDUE notifies holders of the remittance
approving permission, the custodian and whoever recorded their collections that day. Re-running is idempotent.

Unremitted = outstanding custody - remittances already claimed (awaiting confirmation) - approved retentions."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import DbScope, apply_scope
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.custody_models import RemittanceOverdue
from asseta.modules.finance.custody_rules import cash_policy, cutoff_window, day_collection_recorders
from asseta.modules.identity.principal import RequestContext
from asseta.modules.notification.engine import NotificationEngine
from asseta.modules.notification.rules import Audience, Intent, perm, record_link, staff, user
from asseta.modules.notification.settings import get_notification_settings
from asseta.modules.tenancy.models import Tenant, TenantSettings, TenantStatus

log = structlog.get_logger()
SWEEP = AuditActor(None, [], "scheduler")
APPROVE_PERMISSION = "tenant.finance.verify"  # confirms remittances: the people who chase an overdue one


@dataclass
class CutoffSummary:
    tenants: int = 0
    flagged: int = 0
    notifications: int = 0
    failures: int = 0


def _money(value: Decimal) -> str:
    return f"{value.normalize():f}"


def sweep_tenant(s: Session, tenant_id: uuid.UUID, now: datetime) -> list[Intent]:
    """Flag this tenant's overdue custodians for today (inside its RLS scope); returns the notification intents of
    the rows created by this run (none when the policy is off, before the cut-off, or already flagged today)."""
    eff = cash_policy(s, tenant_id, now)  # CASH_CUSTODY switched off: no cut-off (sweep skipped)
    cutoff = eff.policy.remittance_cutoff_hour
    if cutoff is None:
        return []
    ts = s.get(TenantSettings, tenant_id)
    tz = ZoneInfo(ts.timezone if ts else "UTC")
    local = now.astimezone(tz)
    if local.hour < cutoff:
        return []
    day = local.date()
    cutoff_at = datetime.combine(day, time(hour=cutoff), tz)
    ctx = RequestContext(
        uuid.UUID(int=0), "system:remittance-cutoff", DbScope.TENANT, tenant_id, frozenset(), frozenset()
    )
    custody = CashCustodyService(s, ctx, now)
    intents: list[Intent] = []
    for member in custody.custodians():
        amounts = []
        for bal in custody.balances(member.id):
            unremitted = bal.outstanding - bal.claimed_unverified_handovers - bal.approved_retention
            if unremitted <= 0:
                continue
            _, since = custody.outstanding_since(member.id, bal.currency)
            if since is None or since >= cutoff_at:
                continue  # cash received after today's cut-off is due tomorrow
            amounts.append({"currency": bal.currency, "amount": _money(unremitted)})
        if not amounts:
            continue
        row_id = s.execute(
            insert(RemittanceOverdue)
            .values(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                staff_member_id=member.id,
                local_day=day,
                cutoff_hour=cutoff,
                amounts=amounts,
                flagged_at=now,
                policy_version=eff.version_stamp[:80],
            )
            .on_conflict_do_nothing(constraint="uq_cash_remittance_overdue_day")
            .returning(RemittanceOverdue.id)
        ).scalar_one_or_none()
        if row_id is None:
            continue  # already flagged today
        AuditService(s).record(
            actor=SWEEP,
            action="finance.remittance.overdue_flagged",
            entity_type="cash_remittance_overdue",
            entity_id=row_id,
            tenant_id=tenant_id,
            after={"staff_member_id": str(member.id), "day": day.isoformat(), "amounts": amounts},
            policy_version=eff.version_stamp[:64],
        )
        recorders = sorted(day_collection_recorders(s, member.id, *cutoff_window(s, tenant_id, day, cutoff)))
        audiences: list[Audience] = [perm(APPROVE_PERMISSION), staff(member.id), *(user(u) for u in recorders)]
        held = ", ".join(f"{a['currency']} {a['amount']}" for a in amounts)
        intents.append(
            Intent(
                "REMITTANCE_OVERDUE",
                tuple(audiences),
                f"Remittance overdue: {member.full_name}",
                f"{member.full_name} still holds {held} not remitted after the {cutoff:02d}:00 cut-off on {day}.",
                f"remittance-overdue:{row_id}",
                record_link("cash_remittance_overdue", row_id, "/tenant/finance/cash"),
                "cash_remittance_overdue",
                str(row_id),
                data={"staff_member_id": str(member.id), "day": day.isoformat(), "amounts": amounts},
            )
        )
    return intents


def run_remittance_cutoff(session_factory: Callable[[], Session], now: datetime) -> CutoffSummary:
    """One sweep over every non-closed tenant; one tenant's failure never blocks the others."""
    summary = CutoffSummary()
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
                summary.flagged += len(intents)
                if intents:
                    apply_scope(s, DbScope.SYSTEM, None, None)
                    summary.notifications += len(NotificationEngine(s, now.date(), now, cfg).deliver(tid, intents))
        except Exception:
            log.exception("remittance_cutoff_tenant_failed", tenant_id=str(tid))
            summary.failures += 1
    log.info("remittance_cutoff_completed", **summary.__dict__)
    return summary
