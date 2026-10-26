"""Remittance-overdue sweep (REMITTANCE_OVERDUE), two independent tenant rules (both off by default):

- Daily cut-off (`CASH_CUSTODY.remittance_cutoff_hour`, tenant-local; null = off), modelled on the engine-hours
  daily-report check: once the cut-off of the tenant-local day has passed, every custodian still holding unremitted
  cash that they already held before the cut-off is flagged once for that day (reason CUTOFF).
- Holding allowance (`CASH_CUSTODY.max_holding_days`, DEC-031 D3; null = no limit): the tenant default, overridden
  per site (the custodian's current site: the site of the latest in-progress job they supervise or whose machine they
  are assigned to) and per staff member (most specific). A custodian whose oldest unremitted cash (first-in
  first-out) is older than their allowance is flagged once per tenant-local day (reason HELD_TOO_LONG).

Rows are `cash_remittance_overdue`, unique per custodian per day per reason; REMITTANCE_OVERDUE notifies holders of
the remittance approving permission, the custodian and whoever recorded their collections that day. Re-running is
idempotent. With the CASH_CUSTODY capability off both rules read as off.

Unremitted = outstanding custody - remittances already claimed (awaiting confirmation) - approved retentions."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import DbScope, apply_scope
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.custody_models import OverdueReason, RemittanceOverdue
from asseta.modules.finance.custody_rules import cash_policy, cutoff_window, day_collection_recorders
from asseta.modules.fleet.models import MachineAssignment, StaffMember
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import Job, JobStatus
from asseta.modules.notification.engine import NotificationEngine
from asseta.modules.notification.rules import Audience, Intent, perm, record_link, staff, user
from asseta.modules.notification.settings import get_notification_settings
from asseta.modules.policy.service import PolicyService
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


def custodian_site(s: Session, staff_id: uuid.UUID) -> uuid.UUID | None:
    """The custodian's current site: the site of the most recently started in-progress job they supervise or whose
    machine is assigned to them (None when they are on no running job)."""
    assigned = select(MachineAssignment.machine_id).where(
        MachineAssignment.staff_member_id == staff_id, MachineAssignment.effective_to.is_(None)
    )
    return s.execute(
        select(Job.job_site_id)
        .where(
            Job.status == JobStatus.IN_PROGRESS,
            Job.job_site_id.is_not(None),
            or_(Job.supervisor_id == staff_id, Job.machine_id.in_(assigned)),
        )
        .order_by(Job.started_at.desc().nulls_last(), Job.id)
        .limit(1)
    ).scalar_one_or_none()


def holding_allowance(s: Session, tenant_id: uuid.UUID, staff_id: uuid.UUID, now: datetime) -> tuple[int | None, str]:
    """The custodian's `max_holding_days` in force (tenant -> site -> staff) and the policy version stamp."""
    eff = PolicyService(s).cash_custody(tenant_id, at=now, site_id=custodian_site(s, staff_id), staff_id=staff_id)
    return eff.policy.in_force().max_holding_days, eff.version_stamp


def _intent(
    s: Session,
    tenant_id: uuid.UUID,
    member: StaffMember,
    row_id: uuid.UUID,
    day: Any,
    amounts: list[dict[str, str]],
    reason: OverdueReason,
    window: tuple[datetime, datetime],
    extra: dict[str, Any],
    body: str,
) -> Intent:
    recorders = sorted(day_collection_recorders(s, member.id, *window))
    audiences: list[Audience] = [perm(APPROVE_PERMISSION), staff(member.id), *(user(u) for u in recorders)]
    return Intent(
        "REMITTANCE_OVERDUE",
        tuple(audiences),
        f"Remittance overdue: {member.full_name}",
        body,
        f"remittance-overdue:{row_id}",
        record_link("cash_remittance_overdue", row_id, "/tenant/finance/cash"),
        "cash_remittance_overdue",
        str(row_id),
        data={
            "staff_member_id": str(member.id),
            "day": day.isoformat(),
            "amounts": amounts,
            "reason": reason.value,
            **extra,
        },
    )


def _flag(
    s: Session,
    tenant_id: uuid.UUID,
    member: StaffMember,
    day: Any,
    hour: int,
    amounts: list[dict[str, str]],
    now: datetime,
    stamp: str,
    reason: OverdueReason,
    held_since: datetime | None = None,
    max_days: int | None = None,
) -> uuid.UUID | None:
    """Insert the day's flag for this reason; None when it already exists (idempotent)."""
    row_id = s.execute(
        insert(RemittanceOverdue)
        .values(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            staff_member_id=member.id,
            local_day=day,
            cutoff_hour=hour,
            amounts=amounts,
            flagged_at=now,
            policy_version=stamp[:80],
            reason=reason.value,
            held_since=held_since,
            max_holding_days=max_days,
        )
        .on_conflict_do_nothing(constraint="uq_cash_remittance_overdue_day_reason")
        .returning(RemittanceOverdue.id)
    ).scalar_one_or_none()
    if row_id is not None:
        AuditService(s).record(
            actor=SWEEP,
            action="finance.remittance.overdue_flagged",
            entity_type="cash_remittance_overdue",
            entity_id=row_id,
            tenant_id=tenant_id,
            after={
                "staff_member_id": str(member.id),
                "day": day.isoformat(),
                "amounts": amounts,
                "reason": reason.value,
                "held_since": held_since.isoformat() if held_since else None,
                "max_holding_days": max_days,
            },
            policy_version=stamp[:64],
        )
    return row_id


def sweep_tenant(s: Session, tenant_id: uuid.UUID, now: datetime) -> list[Intent]:
    """Flag this tenant's overdue custodians for today (inside its RLS scope); returns the notification intents of
    the rows created by this run (none when both rules are off, before the cut-off, or already flagged today)."""
    eff = cash_policy(s, tenant_id, now)  # CASH_CUSTODY switched off: no cut-off and no holding allowance
    if not PolicyService(s).cash_custody(tenant_id, at=now).policy.enabled:
        return []
    cutoff = eff.policy.remittance_cutoff_hour
    allowance_rule = eff.policy.max_holding_days is not None or _has_allowance_overrides(s, tenant_id)
    if cutoff is None and not allowance_rule:
        return []
    ts = s.get(TenantSettings, tenant_id)
    tz = ZoneInfo(ts.timezone if ts else "UTC")
    local = now.astimezone(tz)
    day = local.date()
    day_start = datetime.combine(day, time(), tz)
    cutoff_due = cutoff is not None and local.hour >= cutoff
    cutoff_at = datetime.combine(day, time(hour=cutoff), tz) if cutoff is not None else None
    ctx = RequestContext(
        uuid.UUID(int=0), "system:remittance-cutoff", DbScope.TENANT, tenant_id, frozenset(), frozenset()
    )
    custody = CashCustodyService(s, ctx, now)
    intents: list[Intent] = []
    for member in custody.custodians():
        balances = custody.balances(member.id)
        if cutoff_due and cutoff_at is not None:
            amounts = []
            for bal in balances:
                unremitted = bal.outstanding - bal.claimed_unverified_handovers - bal.approved_retention
                if unremitted <= 0:
                    continue
                _, since = custody.outstanding_since(member.id, bal.currency)
                if since is None or since >= cutoff_at:
                    continue  # cash received after today's cut-off is due tomorrow
                amounts.append({"currency": bal.currency, "amount": _money(unremitted)})
            assert cutoff is not None
            stamp = eff.version_stamp
            if amounts and (
                row_id := _flag(s, tenant_id, member, day, cutoff, amounts, now, stamp, OverdueReason.CUTOFF)
            ):
                held = ", ".join(f"{a['currency']} {a['amount']}" for a in amounts)
                intents.append(
                    _intent(
                        s,
                        tenant_id,
                        member,
                        row_id,
                        day,
                        amounts,
                        OverdueReason.CUTOFF,
                        cutoff_window(s, tenant_id, day, cutoff),
                        {},
                        f"{member.full_name} still holds {held} not remitted after the {cutoff:02d}:00 cut-off "
                        f"on {day}.",
                    )
                )
        if not allowance_rule:
            continue
        max_days, stamp = holding_allowance(s, tenant_id, member.id, now)
        if max_days is None:
            continue
        amounts, oldest = [], None
        for bal in balances:
            unremitted, since = custody.unremitted_since(member.id, bal.currency)
            if since is None or since + timedelta(days=max_days) > now:
                continue
            amounts.append({"currency": bal.currency, "amount": _money(unremitted)})
            oldest = since if oldest is None else min(oldest, since)
        if not amounts or oldest is None:
            continue
        row_id = _flag(
            s,
            tenant_id,
            member,
            day,
            local.hour,
            amounts,
            now,
            stamp,
            OverdueReason.HELD_TOO_LONG,
            held_since=oldest,
            max_days=max_days,
        )
        if row_id is None:
            continue
        held = ", ".join(f"{a['currency']} {a['amount']}" for a in amounts)
        since_day = oldest.astimezone(tz).date()
        plural = "day" if max_days == 1 else "days"
        intents.append(
            _intent(
                s,
                tenant_id,
                member,
                row_id,
                day,
                amounts,
                OverdueReason.HELD_TOO_LONG,
                (day_start, now),
                {"held_since": oldest.isoformat(), "max_holding_days": max_days},
                f"{member.full_name} has held {held} since {since_day}, longer than the allowed "
                f"{max_days} {plural}. Please remit or explain.",
            )
        )
    return intents


def _has_allowance_overrides(s: Session, tenant_id: uuid.UUID) -> bool:
    """Whether any site/staff override of `max_holding_days` exists (the tenant default may be null)."""
    from asseta.modules.policy.models import PolicyVersion  # local: keep the policy model out of the import path
    from asseta.modules.policy.schemas import PolicyScope, PolicyType

    return (
        s.execute(
            select(PolicyVersion.id)
            .where(
                PolicyVersion.policy_type == PolicyType.CASH_CUSTODY,
                PolicyVersion.tenant_id == tenant_id,
                PolicyVersion.scope.in_((PolicyScope.SITE, PolicyScope.STAFF)),
                PolicyVersion.values.has_key("max_holding_days"),
            )
            .limit(1)
        ).first()
        is not None
    )


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
